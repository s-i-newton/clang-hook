"""Simple output handler"""
import json
import typing
import collections

from .stage import Stage, Stage_to_str
from .filter import InvalidStage
from .abstract_output_handler import AbstractOutputHandler


class OutputHandler(AbstractOutputHandler):
    """Output handler used in standalone mode."""
    def __init__(self, config, logger):
        super(OutputHandler, self).__init__(config, logger)

        def load(path, fields):
            """Helper to load a partial output/report file and initialize it if invalid or empty."""
            try:
                fd = open(path)
            except FileNotFoundError:
                open(path, "w").close()
                fd = open(path)
            try:
                obj = json.load(fd)
                if obj["config"] != self.config.data:
                    self.logger.panic("Current config and %s config does not match" % path)
            except json.JSONDecodeError:
                obj = {"config": config.data}
                for field in fields:
                    obj[field] = []
            finally:
                fd.close()
            return obj

        self.output_obj = load(config.output_file, ["compils"])
        self.report_obj = load(config.report_file, ["compils", "summary"])

    def handle_output(self,
                      output: str,
                      stage: Stage,
                      input_file: typing.Union[str, typing.List[str]],
                      output_file: typing.Union[str, typing.List[str]]):
        """Runs filter on the output of underlying commands."""
        if stage in self.config.output_stages:
            self.output_obj["compils"].append(
                {
                    "stage": Stage_to_str(stage),
                    "input_file": input_file,
                    "output_file": output_file,
                    "stdout": output
                })
        compile_obj = {
            "c_file": input_file,
            "obj_file": output_file,
            "stage": Stage_to_str(stage),
            "matches": []}
        lines = output.strip("\n").split("\n")
        to_log = False
        for line in lines:
            for f in self.config.filters:
                try:
                    match = f.search(line, stage)
                    if match is not None:
                        compile_obj["matches"].append({"name": f.name, "match": match})
                        to_log = True
                except InvalidStage:
                    pass

        if to_log:
            self.report_obj["compils"].append(compile_obj)

    def make_summary(self, input_files: typing.List[str], output_file: str):
        """Make the summary of all reports"""
        summary_obj = {
            "executable": output_file,
            "obj_files": input_files,
            "results": []
        }
        results = {}
        for compil in self.report_obj["compils"]:
            if compil["obj_file"] in input_files:
                for match in compil["matches"]:
                    if match["name"] in results:
                        results[match["name"]].append(match["match"])
                    else:
                        results[match["name"]] = [match["match"]]
        for f in self.config.filters:
            if f.name in results:
                if f.summary == "sum":
                    results[f.name] = sum(results[f.name])
                elif f.summary == "mean":
                    results[f.name] = sum(results[f.name])/len(results[f.name])
                elif f.summary == "append":
                    pass  # Indeed, resulsts is built with the list of all matches.
                elif f.summary == "number":
                    results[f.name] = len(results[f.name])
                elif f.summary == "or":
                    results[f.name] = any(results[f.name])
                elif f.summary == "and":
                    results[f.name] = all(results[f.name])
                elif f.summary == "count":
                    results[f.name] = dict(collections.Counter(results[f.name]))

        summary_obj["results"] = [{"name": k, "result": v} for k, v in results.items()]
        self.report_obj["summary"].append(summary_obj)

    def finalize(self):
        """Finalize the output files."""
        with open(self. config.output_file, "w") as fd:
            json.dump(self.output_obj, fd, indent=4)

        with open(self. config.report_file, "w") as fd:
            json.dump(self.report_obj, fd, indent=4)
