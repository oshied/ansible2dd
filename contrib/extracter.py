#!/usr/bin/python3
# Extract Ansible tasks from tripleo repos

import os
import yaml


TASK_ATTRS = [
    "action",
    "any_errors_fatal",
    "args",
    "async",
    "become",
    "become_exe",
    "become_flags",
    "become_method",
    "become_user",
    "changed_when",
    "check_mode",
    "collections",
    "connection",
    "debugger",
    "delay",
    "delegate_facts",
    "delegate_to",
    "diff",
    "environment",
    "failed_when",
    "ignore_errors",
    "ignore_unreachable",
    "local_action",
    "loop",
    "loop_control",
    "module_defaults",
    "name",
    "no_log",
    "notify",
    "poll",
    "port",
    "register",
    "remote_user",
    "retries",
    "run_once",
    "tags",
    "throttle",
    "timeout",
    "until",
    "vars",
    "when",
    "with_",
]


def get_task_action(task):
    """Return the action of the task."""
    if "action" in task or "local_action" in task:
        action = "action" if "action" in task else "local_action"
        if "module" in task[action]:
            # - action:
            #     module: copy
            #     args:
            #       src: a
            #       dest: b
            return task[action]["module"]
        # - action: copy src=a dest=b
        return task[action].split()[0]
    with_items = []
    for t in task:
        if t.startswith("with_"):
            with_items.append(t)
    action = set(list(task.keys())).difference(set(TASK_ATTRS + with_items))

    if len(action) > 1:
        raise Exception(f"Task has more than one action: {task}")
    if len(action) == 0:
        raise Exception(f"Can't get action from task: {task}")
    action = list(action)[0]
    if action.startswith("ansible.builtin"):
        return action.split(".")[-1]
    return action


def stats_print(stats, output):
    """Print stats."""
    tasks = {}
    result = []
    for i in stats:
        if i in tasks:
            tasks[i] += 1
        else:
            tasks[i] = 1
    for z in sorted(tasks.items(), key=lambda x: x[1], reverse=True):
        result.append("{:<40}  {}".format(z[0], z[1]))
    str_result = "\n".join(result)
    if output == "-":
        print(str_result)
    else:
        with open(output, "w") as f:
            f.write(str_result)


def directory_parse(directory):
    """Parse directory."""
    result = []
    for root, dirs, files in os.walk(directory):
        if files and "molecule" not in root:
            for f in files:
                if (
                    f.endswith(".yml")
                    or f.endswith(".yaml")
                    and "puppet" not in f
                ):
                    result.append(file_parse(os.path.join(root, f)))
    return result


def file_parse(file):
    """Parse file."""
    result = []
    with open(file, "r") as f:
        try:
            y = yaml.load(f, Loader=yaml.FullLoader)
        except yaml.scanner.ScannerError as ye:
            print(f"Error parsing YAML in {file}: {ye}")
            return result
        if y:
            for task in y:
                try:
                    if isinstance(task, str):
                        continue
                    if "block" in task:
                        for i in task["block"]:
                            result.append(get_task_action(i))
                    elif "hosts" in task:
                        for i in (
                            task.get("tasks", [])
                            + task.get("pre_tasks", [])
                            + task.get("post_tasks", [])
                        ):
                            result.append(get_task_action(i))
                    # in case of heat templates
                    elif "outputs" in task:
                        heat_tasks = []
                        if "role_data" in task["outputs"]:
                            new_tasks = task["outputs"]["role_data"]
                            for prep in (
                                "upgrade_tasks",
                                "pre_upgrade_rolling_tasks",
                                "post_upgrade_tasks",
                                "update_tasks",
                                "post_update_tasks",
                                "host_prep_tasks",
                                "external_deploy_tasks",
                                "external_post_deploy_tasks",
                            ):
                                heat_tasks += new_tasks.get(prep, [])
                            for i in heat_tasks:
                                result.append(get_task_action(i))
                    else:
                        action = get_task_action(task)
                        result.append(action)
                except Exception as e:
                    print(f"Error in file: {file}: {e}")
                    continue

    return result


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract tasks from a playbook."
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file. Default: stdout.",
        default="-",
    )
    parser.add_argument(
        "files",
        nargs="*",
        default="tmp.yml",
        help="Files to extract tasks from.",
    )
    args = parser.parse_args()
    result = []
    for f in args.files:
        if os.path.isdir(f):
            for r in directory_parse(f):
                result.extend(r)
        elif os.path.isfile(f):
            result.extend(file_parse(f))
    stats_print(result, args.output)


if __name__ == "__main__":
    main()
