from os import walk
from os.path import join
from sys import exit

from _kanachan import Kanachan
from convert_majsoul_to_mjai import parse_file


def process_messages(kanachan, messages):
    print(f"mjai_message_sub_list: {messages}")
    result = kanachan.run(messages)
    if "type" not in result:
        raise RuntimeError(f"kanachan error {result}")
    if result["type"] == "none":
        return
    print(f"kanachan: {result}")


def traverse_directory(path):
    for root, directories, files in walk(path):
        for file in files:
            file_path = join(root, file)
            # 在这里对每个文件执行你想要的操作
            print(f"reviewer_records file={file} id=0")
            reviewer_records(input_file_name=file_path, id=0)
            # print(f"reviewer_records file={file} id=1")
            # reviewer_records(input_file_name=file_path, id=1)
            # print(f"reviewer_records file={file} id=2")
            # reviewer_records(input_file_name=file_path, id=2)
            # print(f"reviewer_records file={file} id=3")
            # reviewer_records(input_file_name=file_path, id=3)
            exit(0)


def reviewer_records(*, input_file_name: str, id: int):
    kanachan = Kanachan()

    mjai_message_list = parse_file(input_file_name=input_file_name, id=id)

    mjai_message_sub_list = []
    for mjai_message in mjai_message_list:
        if "type" not in mjai_message:
            raise Exception(f"mjai_message.type not in mjai_message: {mjai_message}")

        type = mjai_message["type"]
        actor_is_id = mjai_message.get("actor") == id

        # Define a set of message types that should trigger processing
        process_types = {"start_game", "dahai", "end_kyoku"}

        # Define a set of message types that should also consider the actor ID
        actor_specific_types = {
            "tsumo",
            "pon",
            "chi",
            "kakan",
            "daiminkan",
            "ankan",
            "reach",
        }

        mjai_message_sub_list.append(mjai_message)

        # Check if the current message type is in the process types or is actor-specific and matches the ID
        if type in process_types or (type in actor_specific_types and actor_is_id):
            process_messages(kanachan, mjai_message_sub_list)
            mjai_message_sub_list = []


if __name__ == "__main__":
    traverse_directory(path="G:\\majsoul\\record-data")
    exit(0)
