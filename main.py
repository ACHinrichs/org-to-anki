import orgparse
import genanki
import os
import argparse
from html import escape
import re
import uuid


def htmlify(text):
    # text = text.strip()
    # Remove the leading stars
    text = text.lstrip("*")
    # Escape the text
    text = escape(text)
    # Replace /emphasis/ with <em>emphasis</em>
    # use a regular expression to do this, as /emphasis/ is always
    # surrounded by spaces or newlines
    # The regular expression should match either the beginning of the string or space, followed by a /, then any number of characters that are not /, then a /, then either a space or the end of the string
    text = re.sub(r"/([^/]+)/", r" <em>\1</em> ", text)
    # Replace *bold* with <strong>bold</strong>
    text = re.sub(r"\*([^\*]+)\*", r" <strong>\1</strong> ", text)
    # Replace =code= with <code>code</code>
    text = re.sub(r" =([^=]+)= ", r" <code>\1</code> ", text)
    # parse lists
    # if a line starts with a - surrounded by spaces, it is a list item
    # the number of spaces before the - determines the level of the list
    # we will replace the - with a <li> tag and for a levelchange add a <ul> or </ul> tag
    # we will also remove the leading spaces
    # 0 spaces before the - is allowed
    list_levels = []  # will be used as a stack
    out_text = ""
    for line in text.split("\n"):
        # print(f"Line: '{line}'")
        if re.match(r"^(\s)*-", line):
            level = len(re.match(r"^\s*", line).group(0))
            # print(f"Level: {level}, List levels: {list_levels}")
            # if the upper most level is smaller than the current level, we have to add a new list
            if len(list_levels) == 0 or list_levels[-1] < level:
                # print("Adding level")
                list_levels.append(level)
                out_text += "<ul>"
            # if the upper most level is greater than the current level, we have to close the list
            elif list_levels[-1] > level:
                out_text += "</ul>"
                list_levels.pop()
            out_text += f"<li>{line.strip()[1:]}</li>"  # remove the leading space and the -, then add the <li> tag
        else:
            # We may have closed lists
            while len(list_levels) > 0:
                out_text += "</ul>"
                list_levels.pop()
            out_text += line.strip()
            out_text += "<br>"
        out_text += "\n"
    # We may have unclosed lists
    while len(list_levels) > 0:
        out_text += "</ul>"
        list_levels.pop()
    # print(f"Text: {out_text}")
    return out_text


def generate_id(namespace, node):
    return str(uuid.uuid5(namespace, node.heading))


class OrgUIDNote(genanki.Note):
    def __init__(self, model, fields, guid=None):
        super().__init__(model, fields, guid)
        self.guid = guid

    def guid_for_fields(self, fields):
        return self.guid


def main():
    # First set up the argument parser
    parser = argparse.ArgumentParser(description="Generate Anki cards from org files")
    parser.add_argument("orgfile", help="The org file to generate cards from")
    parser.add_argument("deckname", help="The name of the deck to create")
    parser.add_argument("outputfile", help="The name of the output file")
    parser.add_argument(
        "--deck_id",
        help="The ID of the deck to create. Required!",
        type=int,
        required=True,
    )
    parser.add_argument(
        "--create_ids", help="Create unique IDs for each card", action="store_true"
    )
    parser.add_argument(
        "--rewrite_orgfile",
        help="Rewrite the org file with the UUIDs of the cards, do this at your own risk",
        action="store_true",
    )
    args = parser.parse_args()

    # Load the org file
    org = orgparse.load(args.orgfile)

    # Create the deck
    deck = genanki.Deck(args.deck_id, args.deckname)

    # Create the model
    model = genanki.Model(
        1607392319,
        "Simple Model",
        fields=[
            {"name": "Question"},
            {"name": "Answer"},
        ],
        templates=[
            {
                "name": "Card 1",
                "qfmt": "{{Question}}",
                "afmt": '{{FrontSide}}<hr id="answer">{{Answer}}',
            },
        ],
    )

    # Add the model to the deck
    deck.add_model(model)

    # Add the notes to the deck
    for node in org:
        if isinstance(node, orgparse.OrgNode):
            # ignore :no-export: tag
            if "no-export" in node.tags:
                continue
            if args.create_ids:
                # check if the node has an ID, if not, create one
                if node.get_property("ID") == "" or node.get_property("ID") is None:
                    node.properties["ID"] = generate_id(uuid.NAMESPACE_DNS, node)
            # Create a note, html encode the heading and body
            question = htmlify(node.heading)
            answer = htmlify(node.body)
            if node.body == "":
                continue
            note = OrgUIDNote(
                model=model, fields=[question, answer], guid=node.get_property("ID")
            )
            deck.add_note(note)

    # create and write the deck
    package = genanki.Package(deck)
    package.write_to_file(args.outputfile)

    # rewrite the org file
    if args.rewrite_orgfile:
        with open(args.orgfile, "w") as f:
            for node in org:
                # we can't just cast to string here, because that would
                # remove the new properties. THerefore we have to rebuild
                # the node
                if isinstance(node, orgparse.OrgNode):
                    f.write(f'{"*"*node.level} {node.get_heading(format="raw")}')
                    if len(node.shallow_tags) > 0:
                        f.write(" ")
                        for tag in sorted(node.tags):
                            f.write(f":{tag}")
                        f.write(":")
                    f.write("\n")
                if len(node.properties) > 0:
                    f.write(f":PROPERTIES:\n")
                    for prop in node.properties:
                        f.write(f":{prop}: {node.get_property(prop)}\n")
                    f.write(":END:\n")
                f.write(node.get_body(format="raw"))
                f.write("\n")


# call main
if __name__ == "__main__":
    main()
