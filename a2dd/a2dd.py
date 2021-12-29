#   Copyright Sagi Shnaidman <sshnaidm@redhat.com>. All Rights Reserved.
#
#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.

from ruamel.yaml.comments import CommentedMap as Map

from a2dd.constants import BLOCK_ATTRS, PLAYBOOK_ATTRS, TASK_ATTRS
from a2dd.utils import get_task_action, yaml_dump, yaml_load


class AnsibleTask:
    """AnsibleTask class parses a single task."""

    def __init__(self, task, block=None, include=None, role=None, play=None):
        """Set context for task.

        Args:
            task (dict): Task loaded from YAML to parse
            block (dict, optional): Block context. Defaults to None.
            include (dict, optional): Include context. Defaults to None.
            role (dict, optional): Role context. Defaults to None.
            play (dict, optional): Playbook context. Defaults to None.
        """
        self.task = task
        self.block = block
        self.include = include
        self.role = role
        self.play = play

    def parse(self):
        """Parser for task.

        Raises:
            ValueError: if task is block or include

        Returns:
            list: List of DirectorD tasks with comments as ruamel Maps
        """
        task_module = get_task_action(self.task)
        # Let's assume task names are unique in all collections we use
        # Remove collection part of it
        if "." in task_module:
            new_task_module = task_module.split(".")[-1]
            self.task[new_task_module] = self.task.pop(task_module)
            task_module = new_task_module
        if task_module in ("block", "include", "include_tasks"):
            raise ValueError(
                f"Can not parse module {task_module} - "
                "use a specific class for it"
            )
        parsed_attrs = (task_module, "name")
        task_args = {
            k: v for k, v in self.task.items() if k not in parsed_attrs
        }
        name = self.task.get("name", "Unnamed task")

        func_name = "task_" + task_module
        tasks_parsed = []
        if not hasattr(self, func_name):
            task_context = yaml_dump(self.task)
            tasks_parsed = [
                Map(
                    {
                        "NAME": name,
                        "ECHO": (
                            f"Conversion of task module '{task_module}' is not"
                            " implemented yet!"
                        ),
                    }
                )
            ]
        else:
            parsed, task_context = getattr(self, func_name)(task_args)
            if parsed:
                for each_task in parsed:
                    named_task = {"NAME": name}  # for NAME to be on the top
                    named_task.update(each_task)
                    tasks_parsed.append(Map(named_task))
            if task_context:
                task_context = yaml_dump(task_context)

        context = ""
        if task_context:
            context = f"TASK-CONTEXT:\n{task_context}"
        for add_context in (self.block, self.include, self.role, self.play):
            if add_context and "context" in add_context:
                context = "\n".join([add_context["context"], context])
        context = f"\n{context}"
        if context:
            for task in tasks_parsed:
                task.yaml_set_start_comment(context)
        return tasks_parsed

    def task_shell(self, task_args):
        """Parse shell task.

        Args:
            task_args (dict): task loaded from YAML

        Raises:
            ValueError: if shell command is not found in task

        Returns:
            tuple: (list, list) : List of DirectorD tasks as dictionaries with
                                  list of unparsed lines as comments.
        """
        exe = []
        action = "shell" if "shell" in self.task else "command"
        run = self.task[action]
        if isinstance(run, dict):
            if "args" in self.task and "cmd" in self.task["args"]:
                run = self.task["args"]["cmd"]
            if "cmd" in run:
                run = run["cmd"]
        if not isinstance(run, str):
            raise ValueError(f"Can not get shell command from: {self.task}")
        if "chdir" in self.task.get("args", {}):
            exe.append(f'cd {self.task["args"]["chdir"]};')
        elif "chdir" in self.task[action]:
            exe.append(f'cd {self.task[action]["chdir"]};')
        for env in [
            i for i in (self.play, self.block, self.task) if i is not None
        ]:
            if "environment" in env:
                for k, v in env["environment"].items():
                    exe.append(f'export {k}="{v}";')
        exe.append(run)
        # Not parsed lines go to task-context for future implementation
        for i in ("environment", "chdir", "name", "args"):
            task_args.pop(i, None)
        return [{"RUN": "\n".join(exe)}], task_args

    def task_command(self, task_args):
        """Parse command task.

        Args:
            task_args (dict): task loaded from YAML

        Raises:
            ValueError: if command is not found in task

        Returns:
            tuple: (list, list) : List of DirectorD tasks as dictionaries with
                                  list of unparsed lines as comments.
        """
        return self.task_shell(task_args)

    def task_set_fact(self, task_args):
        """Parse set_fact task.

        Args:
            task_args (dict): task loaded from YAML

        Returns:
            tuple: (list, list) : List of DirectorD tasks as dictionaries with
                                  list of unparsed lines as comments.
        """
        args = []
        for arg in list(self.task["set_fact"].items()):
            if arg[0] != "cacheable":
                args.append({"ARG": f'{arg[0]} "{arg[1]}"'})
        return args, task_args

    def task_dnf(self, task_args):
        """Parse dnf task.

        Args:
            task_args (dict): task loaded from YAML

        Returns:
            tuple: (list, list) : List of DirectorD tasks as dictionaries with
                                  list of unparsed lines as comments.
        """
        args = []
        pkgs = self.task["dnf"]["name"]
        state = self.task["dnf"].get("state", "present")
        if pkgs == "*" and state == "latest":
            return [{"RUN": "dnf update -y"}], task_args

        if isinstance(pkgs, str):
            pkgs = [pkgs]
        if state == "latest":
            args.append("--latest")
        elif state == "absent":
            args.append("--absent")

        for k, v in self.task["dnf"].items():
            if k not in ("name", "state"):
                raise ValueError(f"Not implemented key in dnf task: {k}: {v}")
        dnf = [{"DNF": " ".join(args + pkgs)}]
        return dnf, task_args

    def task_setup(self, task_args):
        """Parse setup task.

        Args:
            task_args (dict): task loaded from YAML

        Returns:
            tuple: (list, list) : List of DirectorD tasks as dictionaries with
                                  list of unparsed lines as comments.
        """
        # We don't have filters now, just run facter for all
        setup = [{"FACTER": ""}]
        return setup, task_args


class AnsibleBlock:
    """AnsibleBlock class parses a single tasks block."""

    def __init__(self, block, **kwargs):
        """Parse a block of tasks, passing all context arguments to tasks.

        Args:
            block (dict): Dictionary of block loaded from YAML
        """
        self.block = block
        self.kwargs = kwargs

    def add_context(self):
        """Add block context - all options which we don't parse currently.

        Returns:
            str: Block context as commented lines
        """
        block_context = ["## BLOCK-CONTEXT:"]
        for part in self.block:
            if part in BLOCK_ATTRS and part not in ("block", "environment"):
                block_context.append(f"{part}: {self.block[part]}")
        return "\n".join(block_context)

    def parse(self):
        """Parse block of tasks.

        Returns:
            list: List of maps with parsed tasks.
        """
        result = []
        if "environment" in self.block:
            for k, v in self.block["environment"].items():
                result.append(
                    Map(
                        {
                            "NAME": f"Set block env value for {k}",
                            "ENV": f"{k} {v}",
                        }
                    )
                )

        self.block["context"] = self.add_context()
        result = AnsibleTasksList(
            self.block["block"], block=self.block, **self.kwargs
        ).parse()
        return result


class AnsibleIncludeTasks:
    """AnsibleIncludeTasks class parses a tasks file from include block."""

    def __init__(self, include, **kwargs):
        """Parse included file of tasks, passing all context argument to tasks.

        Args:
            include (dict): Dictionary of include task loaded from YAML
        """
        self.include = include
        self.kwargs = kwargs

    def add_context(self):
        """Add inlcude context - all options which we don't parse currently.

        Returns:
            str: Include context as commented lines
        """
        include_context = ["## INCLUDE-CONTEXT:"]
        for part in self.include:
            if part in TASK_ATTRS and part not in (
                "include",
                "include_tasks",
                "environment",
            ):
                include_context.append(f"{part}: {self.include[part]}")
        return "\n".join(include_context)

    def parse(self):
        """Parse file with tasks.

        Returns:
            list: List of maps with parsed tasks.
        """
        result = []
        if "environment" in self.include:
            for k, v in self.include["environment"].items():
                result.append(
                    Map(
                        {
                            "NAME": f"Set include env value for {k}",
                            "ENV": f"{k} {v}",
                        }
                    )
                )

        self.include["context"] = self.add_context()
        tasks_file = self.include.get("include") or self.include.get(
            "include_tasks"
        )
        with open(tasks_file, "r", encoding="utf-8") as f:
            tasks = yaml_load(f)
        result = AnsibleTasksList(
            tasks, include=self.include, **self.kwargs
        ).parse()
        return result


class AnsibleTasksList:
    """AnsibleTasksList class parses any list of tasks."""

    def __init__(self, tasks, **kwargs):
        """Parse a list of tasks, passing all context arguments to tasks.

        Args:
            tasks (list): List of tasks loaded from YAML
        """
        self.tasks = tasks
        self.kwargs = kwargs

    def parse(self):
        """Parse a list of tasks and return a flattened list.

        Returns:
            list: List of maps with parsed tasks.
        """
        result = []
        for task in self.tasks:
            if "block" in task:
                block = AnsibleBlock(task, **self.kwargs)
                result.extend(block.parse())
            elif (
                "include" in task
                or "include_tasks" in task
                or "import_tasks" in task
            ):
                incl = AnsibleIncludeTasks(task, **self.kwargs)
                result.extend(incl.parse())
            else:
                task_repr = AnsibleTask(task, **self.kwargs)
                result.extend(task_repr.parse())
        return result


class AnsiblePlay:
    """AnsiblePlay class parses a playbook."""

    def __init__(self, playbook):
        """Parse a playbook, passing all context arguments to tasks.

        Args:
            playbook (dict): Dictionary of playbook loaded from YAML
        """
        self.playbook = playbook

    def add_context(self):
        """Add playbook context - all options which we don't parse currently.

        Returns:
            str: Playbook context as commented lines
        """
        play_context = ["## PLAYBOOK-CONTEXT:"]
        for part in self.playbook:
            if part in PLAYBOOK_ATTRS and part not in (
                "environment",
                "hosts",
                "gather_facts",
                "tasks",
                "pre_tasks",
                "post_tasks",
            ):
                play_context.append(f"{part}: {self.playbook[part]}")
        return "\n".join(play_context)

    def parse(self):
        """Parse a playbook.

        Raises:
            NotImplementedError: when roles are not supported

        Returns:
            list: List of maps with parsed tasks.
        """
        play_result = []
        play_dict = {}
        if "environment" in self.playbook:
            for k, v in self.playbook["environment"].items():
                play_result.append(
                    Map(
                        {
                            "NAME": f"Set playbook env value for {k}",
                            "ENV": f"{k} {v}",
                        }
                    )
                )
        if self.playbook.get("gather_facts", False):
            play_result.append(
                Map(
                    {
                        "NAME": "Gather facts for playbook",
                        "FACTER": "",
                    }
                )
            )
        self.playbook["context"] = self.add_context()
        targets = self.playbook["hosts"]
        if targets != "all":
            play_dict["targets"] = targets
        for step in self.playbook:
            if step == "roles":
                raise NotImplementedError("Roles are not supported yet!")
            if step in ("pre-tasks", "tasks", "post-tasks"):
                tasks_list = AnsibleTasksList(
                    self.playbook[step], play=self.playbook
                )
                play_result.extend(tasks_list.parse())
        play_dict.update({"jobs": play_result})
        return play_dict


def vars_parse(vars_path=None):
    """Parse vars file.

    Args:
        vars_path (str, optional): Path to vars file. Defaults to None.

    Raises:
        NotImplementedError: for now
    """
    raise NotImplementedError("Vars parsing is not supported yet!")


def role_parse(role_path=None):
    """Parse a role.

    Args:
        role_path (str, optional): Path to role. Defaults to None.

    Raises:
        NotImplementedError: for now
    """
    raise NotImplementedError("Roles parsing is not supported yet!")


def parse_file(file_path):
    """Parse an arbitrary Ansible file.

    Args:
        file_path (str): Path to Ansible file.

    Returns:
        list: List of maps with parsed tasks.
    """
    result = []
    with open(file_path, "r", encoding="utf-8") as f:
        ansible_file = yaml_load(f)
        if isinstance(ansible_file, list):
            for i in ansible_file:
                if "hosts" in i:
                    play = AnsiblePlay(i)
                    result.append(play.parse())
                else:
                    for task in ansible_file:
                        t = AnsibleTask(task)
                        result.append(t.parse())
        if isinstance(ansible_file, dict):
            result.append(vars_parse(ansible_file))
    return result
