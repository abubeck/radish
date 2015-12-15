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

    def _get_element_from_model(self, what, model):
        """
            Create a etree.Element from a given model
        """
        duration = str(model.duration.total_seconds()) if model.starttime and model.endtime else ""
        return etree.Element(
            what,
            name=model.sentence,
            id=str(model.id),
            #result=model.state,
            #starttime=utils.datetime_to_str(model.starttime),
            #endtime=utils.datetime_to_str(model.endtime),
            time=duration,
            #testfile=model.path
        )

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

        duration = timedelta()
        for feature in features:
            if feature.state in [Step.State.PASSED, Step.State.FAILED]:
                duration += feature.duration

        testsuites_element = etree.Element(
            "testsuites",
            #starttime=utils.datetime_to_str(features[0].starttime),
            #endtime=utils.datetime_to_str(features[-1].endtime),
            time=str(duration.total_seconds()),
            name=features[0].path
            #agent="{0}@{1}".format(getuser(), gethostname())
        )

        for feature in features:
            if not feature.has_to_run(world.config.scenarios, world.config.feature_tags, world.config.scenario_tags):
                continue

            feature_element = self._get_element_from_model("testsuites", feature)

            description_element = etree.Element("description")
            description_element.text = etree.CDATA("\n".join(feature.description))

            for scenario in (s for s in feature.all_scenarios if not isinstance(s, (ScenarioOutline, ScenarioLoop))):
                if not scenario.has_to_run(world.config.scenarios, world.config.feature_tags, world.config.scenario_tags):
                    continue
                scenario_element = self._get_element_from_model("testsuite", scenario)

                for step in scenario.all_steps:
                    step_element = self._get_element_from_model("testcase", step)
                    if step.state is Step.State.FAILED:
                        failure_element = etree.Element(
                            "failure",
                            #type=step.failure.name,
                            message=step.failure.reason
                        )
                        failure_element.text = etree.CDATA(self._strip_ansi(step.failure.traceback))
                        step_element.append(failure_element)
                    scenario_element.append(step_element)
                feature_element.append(scenario_element)
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
