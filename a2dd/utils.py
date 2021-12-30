import ruamel.yaml

from a2dd.constants import TASK_ATTRS


class NewDumper(ruamel.yaml.RoundTripDumper):
    """Wrapper for ruamel.yaml RoundTripDumper class."""

    def should_use_block(self, value):
        """Newline detector for YAML."""
        for c in "\u000a\u000d\u001c\u001d\u001e\u0085\u2028\u2029":
            if c in value:
                return True
        return False

    def represent_scalar(self, tag, value, style=None, anchor=None):
        """Override a represent_scalar method."""
        if style is None:
            if self.should_use_block(value):
                style = "|"
            else:
                style = self.default_style
        comment = None
        if style and style[0] in "|>":
            comment = getattr(value, "comment", None)
            if comment:
                comment = [None, [comment]]
        node = ruamel.yaml.representer.ScalarNode(
            tag, value, style=style, comment=comment, anchor=anchor
        )
        if self.alias_key is not None:
            self.represented_objects[self.alias_key] = node
        return node


def yaml_dump(content):
    """Dump a ruamel.yaml object (dictionary)."""
    return ruamel.yaml.dump(
        content, Dumper=NewDumper, default_flow_style=False
    )


def yaml_load(stringg):
    """Load a ruamel.yaml object (dictionary) from string."""
    return ruamel.yaml.load(
        stringg, ruamel.yaml.RoundTripLoader, version=(1, 1)
    )


def add_comment(ruamel_obj, comment):
    """Add a comment to a ruamel.yaml object."""
    if comment:
        ruamel_obj.yaml_set_start_comment(comment)


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
    return list(action)[0]
