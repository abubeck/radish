# -*- coding: utf-8 -*-

"""
    This module provides a hook which generates a JUnit XML result file at the end of the run.
"""

from getpass import getuser
from socket import gethostname
from lxml import etree
from datetime import timedelta
import re

from radish.terrain import world
from radish.hookregistry import after
from radish.exceptions import RadishError
from radish.scenariooutline import ScenarioOutline
from radish.scenarioloop import ScenarioLoop
from radish.stepmodel import Step
from radish.extensionregistry import extension
import radish.utils as utils


@extension
class JUnitXMLWriter(object):
    """
        JUnit XML Writer radish extension
    """
    OPTIONS = [("--junit-xml=<junitxml>", "write JUnit XML result file after run")]
    LOAD_IF = staticmethod(lambda config: config.junit_xml)
    LOAD_PRIORITY = 60

    def __init__(self):
        after.all(self.generate_junit_xml)

    def _strip_ansi(self, text):
        """
            Strips ANSI modifiers from the given text
        """
        pattern = re.compile("(\\033\[\d+(?:;\d+)*m)")
        return pattern.sub("", text)

    def generate_junit_xml(self, features, marker):
        """
            Generates the junit xml
        """
        if not features:
            raise RadishError("No features given to generate JUnit xml file")

        duration = 0
        for feature in features:
            if feature.state in [Step.State.PASSED, Step.State.FAILED]:
                duration += feature.duration.total_seconds()

        testsuites_element = etree.Element(
            "testsuites",
            time=str(duration),
            name=features[0].path
        )

        for feature in features:
            if not feature.has_to_run(world.config.scenarios, world.config.feature_tags, world.config.scenario_tags):
                continue

            testcase_counter = 0
            failure_counter = 0
            skip_counter = 0
            for scenario in (s for s in feature.all_scenarios if not isinstance(s, (ScenarioOutline, ScenarioLoop))):
                for step in scenario.all_steps:
                    testcase_counter += 1
                    if step.state is Step.State.FAILED:
                        failure_counter += 1

            feature_duration = str(feature.duration.total_seconds()) if feature.starttime and feature.endtime else ""
            feature_element = etree.Element(
                "testsuite",
                name=feature.path,
                tests=str(testcase_counter),
                errors=str(failure_counter),
                skips=str(0),
                time=str(feature_duration)
                )

            for scenario in (s for s in feature.all_scenarios if not isinstance(s, (ScenarioOutline, ScenarioLoop))):
                if not scenario.has_to_run(world.config.scenarios, world.config.feature_tags, world.config.scenario_tags):
                    continue

                for step in scenario.all_steps:
                    step_duration = str(step.duration.total_seconds()) if step.starttime and step.endtime else ""
                    step_element = etree.Element(
                        "testcase",
                        name=step.sentence,
                        classname=feature.path+"."+scenario.sentence,
                        time=str(step_duration)
                    )
                    if step.state is Step.State.FAILED:
                        failure_element = etree.Element(
                            "failure",
                            message=step.failure.reason
                        )
                        failure_element.text = etree.CDATA(self._strip_ansi(step.failure.traceback))
                        step_element.append(failure_element)
                    feature_element.append(step_element)
            testsuites_element.append(feature_element)

        with open(world.config.junit_xml, "w+") as f:
            content = etree.tostring(testsuites_element, pretty_print=True, xml_declaration=True, encoding="utf-8")
            try:
                if not isinstance(content, str):
                    content = content.decode("utf-8")
            except Exception:
                pass
            finally:
                f.write(content)
