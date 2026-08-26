import json
from pathlib import Path
from collections import defaultdict

from GalTransl import LOGGER


class ProblemHandler:
    def __init__(self, cache_dir: str) -> None:
        self.cache_dir = Path(cache_dir)
        self.manifest_file = self.cache_dir / "问题清单.json"

    def save_manifest(self):
        """
        把有问题的对象直接保存在`transl_cache/问题清单.json`中。
        """

        problems_measured_by_index = self._collect_problems()
        sub_problem_list: list = [
            (self._split_problem_str(problem_obj["problem"]), problem_obj)
            for _, problems_in_file in problems_measured_by_index.items()
            for __, problem_obj in problems_in_file.items()
            if problem_obj is not None
        ]

        manifest_json = defaultdict(list)
        for k, v in sub_problem_list:
            manifest_json[k].append(v)

        self.manifest_file.write_text(
            json.dumps(manifest_json, indent=2, ensure_ascii=False), "utf-8"
        )

    def apply_manifest(self) -> bool:
        """
        在最新的问题对象中应用`transl_cache/问题清单.json`中的修改。
        """
        if self.manifest_file.exists():
            fail_list: list[tuple[str, int]] = []
            try:
                problems_json = json.loads(self.manifest_file.read_text("utf-8"))
                problems_measured_by_index = self._collect_problems()
            except json.decoder.JSONDecodeError:
                LOGGER.error(f"{self.manifest_file.name}文件json解析失败！")
                return False

            # 读取和更新需要修改的内容
            for _, objs in problems_json.items():
                for obj in objs:
                    try:
                        file_name = obj.pop("belong_to")
                        if obj.pop("del_this", False):
                            problems_measured_by_index[file_name][obj["index"]] = None
                        else:
                            problems_measured_by_index[file_name][obj["index"]].update(
                                obj
                            )
                    except KeyError:
                        LOGGER.error("有对象缺失index或belong_to属性！")

            # 应用修改
            for filename, index_obj in problems_measured_by_index.items():
                file_path = self.cache_dir / filename

                if not file_path.exists():
                    fail_list.append((filename, -1))
                    continue

                try:
                    raw_objs: list[dict] = json.loads(file_path.read_text("utf-8"))
                except json.decoder.JSONDecodeError:
                    LOGGER.error(f"{file_path.name}文件json解析失败！")
                    continue

                for idx, obj in sorted(index_obj.items(), reverse=True):
                    if idx != raw_objs[idx - 1].get("index", -1):
                        # index不匹配，说明用户在此期间手动修改了cache文件，需要重新匹配
                        for true_idx, raw_obj in enumerate(raw_objs):
                            if raw_obj.get("index", -2) == idx:
                                if obj is None:
                                    raw_objs.pop(true_idx)
                                else:
                                    raw_objs[true_idx].update(obj)
                                break
                        else:
                            fail_list.append((filename, idx))
                    else:
                        if obj is None:
                            raw_objs.pop(idx - 1)
                        else:
                            raw_objs[idx - 1].update(obj)

                file_path.write_text(
                    json.dumps(raw_objs, indent=2, ensure_ascii=False), "utf-8"
                )

            self._logger_fail(fail_list)
            return True
        else:
            return False

    def _collect_problems(self) -> dict[str, dict[int, dict | None]]:
        """
        从`cache`文件夹中收集所有含有`problem`字段的对象并返回。
        """
        problems_measured_by_index = {}
        for cache_file in self.cache_dir.glob("*.json"):
            if cache_file.name != self.manifest_file.name:
                problems_measured_by_index[cache_file.name] = {}

                try:
                    file_json = json.loads(cache_file.read_text("utf-8"))
                except json.decoder.JSONDecodeError:
                    LOGGER.error(f"{cache_file.name}文件json解析失败！")
                    continue
                for obj in file_json:
                    if "problem" in obj:
                        obj["belong_to"] = cache_file.name
                        obj["del_this"] = False

                        problems_measured_by_index[cache_file.name][obj["index"]] = obj
        return problems_measured_by_index

    def _split_problem_str(self, problem_str: str) -> str:
        problems: list = []
        for single in problem_str.split(","):
            single = single.strip()
            if "：" in single:
                single = single.split("：", maxsplit=1)[0]
            problems.append(single)

        return ", ".join(problems)

    def _logger_fail(self, fail_list: list[tuple[str, int]]) -> None:
        for name, idx in fail_list:
            if idx == -1:
                LOGGER.error(f"{name}不存在，修改失败。")
            else:
                LOGGER.error(f"{name}---{idx}不存在，修改失败。")
