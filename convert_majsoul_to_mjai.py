from majsoulliqi import liqi_pb2

# mjai-protocol
# https://mjai.app/docs/mjai-protocol
# Manzu (萬子): "1m", "2m", ..., "9m"
# Pinzu (筒子): "1p", "2p", ..., "9p"
# Souzu (索子): "1s", "2s", ..., "9s"
# Wind (風牌; Kazehai): "E" (東; Ton), "S" (南; Nan), "W" (西; Shaa), "N" (北; Pei)
# Dragon (三元牌; Sangenpai): "P" (白; Haku), "F" (發; Hatsu), "C" (中; Chun)
# Red doragon (赤ドラ; Akadora): "5mr", "5pr", "5sr"
# Unseen tile: "?"

_BAKAZE2MJAI = ("E", "S", "W", "N")
_MJAI2BAKAZE = {"E": 0, "S": 1, "W": 2, "N": 3}

_KYOKU2MJAI = (1, 2, 3, 4)
_MJAI2KYOKU = (0, 1, 2, 3)

_TILES2MJAI = {
    "1m": "1m",
    "2m": "2m",
    "3m": "3m",
    "4m": "4m",
    "5m": "5m",
    "0m": "5mr",
    "6m": "6m",
    "7m": "7m",
    "8m": "8m",
    "9m": "9m",
    "1p": "1p",
    "2p": "2p",
    "3p": "3p",
    "4p": "4p",
    "5p": "5p",
    "0p": "5pr",
    "6p": "6p",
    "7p": "7p",
    "8p": "8p",
    "9p": "9p",
    "1s": "1s",
    "2s": "2s",
    "3s": "3s",
    "4s": "4s",
    "5s": "5s",
    "0s": "5sr",
    "6s": "6s",
    "7s": "7s",
    "8s": "8s",
    "9s": "9s",
    "1z": "E",
    "2z": "S",
    "3z": "W",
    "4z": "N",
    "5z": "P",
    "6z": "F",
    "7z": "C",
}
_MJAI2TILES = {
    "1m": "1m",
    "2m": "2m",
    "3m": "3m",
    "4m": "4m",
    "5m": "5m",
    "5mr": "0m",
    "6m": "6m",
    "7m": "7m",
    "8m": "8m",
    "9m": "9m",
    "1p": "1p",
    "2p": "2p",
    "3p": "3p",
    "4p": "4p",
    "5p": "5p",
    "5pr": "0p",
    "6p": "6p",
    "7p": "7p",
    "8p": "8p",
    "9p": "9p",
    "1s": "1s",
    "2s": "2s",
    "3s": "3s",
    "4s": "4s",
    "5s": "5s",
    "5sr": "0s",
    "6s": "6s",
    "7s": "7s",
    "8s": "8s",
    "9s": "9s",
    "E": "1z",
    "S": "2z",
    "W": "3z",
    "N": "4z",
    "P": "5z",
    "F": "6z",
    "C": "7z",
}


class Operation:
    NoEffect = 0
    Discard = 1
    Chi = 2
    Peng = 3
    AnGang = 4
    MingGang = 5
    JiaGang = 6
    Liqi = 7
    Zimo = 8
    Hu = 9
    LiuJu = 10


class OperationChiPengGang:
    Chi = 0
    Peng = 1
    Gang = 2


class OperationAnGangAddGang:
    AddGang = 2
    AnGang = 3


class RecordConfig:
    def __init__(self):
        pass


class Convert:
    def __init__(self):
        pass

    def parse_message(self):
        pass


def parse_file(input_file_name: str, id: int):
    if -1 > id > 3:
        raise RuntimeError(f'id = {id}, want 0 <= id <= 3')
    mjai_list = []
    with open(input_file_name, mode="rb") as input_file:
        input_file.seek(3)
        data = input_file.read()

        if len(data) == 0:
            raise RuntimeError(f'input_file_name = {input_file_name} length is zero')

        wrapper = liqi_pb2.Wrapper()
        wrapper.ParseFromString(data)

        if wrapper.name:
            raise RuntimeError(f'wrapper.name \n\t want "" \n\t have {wrapper.name}')

        if len(wrapper.data) == 0:
            raise RuntimeError('wrapper.data length is zero')

        res_game_record = liqi_pb2.ResGameRecord()
        res_game_record.ParseFromString(wrapper.data)

        record_game = res_game_record.head
        uuid = record_game.uuid
        config = record_game.config
        mate_data = config.meta
        mode_id = mate_data.mode_id
        levels = [account.level.id for account in record_game.accounts[:4]]

        if len(res_game_record.data) == 0:
            raise RuntimeError('res_game_record.data length is zero')
        wrapper.ParseFromString(res_game_record.data)
        if wrapper.name != '.lq.GameDetailRecords':
            raise RuntimeError(f'wrapper.name \n\t want ".lq.GameDetailRecords" \n\t have {wrapper.name}')
        if len(wrapper.data) == 0:
            raise RuntimeError('wrapper.data length is zero')

        game_detail_records = liqi_pb2.GameDetailRecords()
        game_detail_records.ParseFromString(wrapper.data)

        if game_detail_records.version == 0:
            if len(game_detail_records.actions) != 0:
                raise RuntimeError(
                    f"uuid:{uuid} game_detail_records.version == 0 but len(game_detail_records.actions) "
                    f"== {len(game_detail_records.actions)}"
                )
            records_0 = game_detail_records.records
            record_size = len(game_detail_records.records)
            pass
        elif game_detail_records.version == 210715:
            if len(game_detail_records.records) != 0:
                raise RuntimeError(
                    f"uuid:{uuid} game_detail_records.version == 210715 but len(game_detail_records.records) "
                    f"== {len(game_detail_records.records)}"
                )
            records_210715 = game_detail_records.actions
            record_size = len(game_detail_records.actions)
            pass
        else:
            raise RuntimeError(
                f"uuid:{uuid} gameDetailRecords.version == {game_detail_records.version} is unkown"
            )

        if record_size is None:
            raise RuntimeError(
                f"uuid:{uuid} record_size is None"  # noqa: F821
            )
        if record_size == 0:
            raise RuntimeError(
                f"uuid:{uuid} record_size == 0"
            )

        if records_0 is None and records_210715 is None:
            raise RuntimeError(
                f"uuid:{uuid} records_0 is None and records_210715 is None"
            )

        mjai_list.append({"type": "start_game", "id": id})

        ld_seat = 0
        doras = []
        liqi = [
            False,
            False,
            False,
            False,
        ]

        for index in range(record_size):
            if game_detail_records.version == 0:
                r = records_0[index]
            elif game_detail_records.version == 210715:
                r = records_210715[index]
            else:
                raise RuntimeError(
                    f"uuid:{uuid} gameDetailRecords.version == {game_detail_records.version} is unkown"
                )

            wrapper.ParseFromString(r)
            if len(wrapper.data) == 0:
                raise RuntimeError(
                    f"uuid:{uuid} wrapper.data length is zero"
                )
            if wrapper.name == ".lq.RecordNewRound":
                ld_seat = 0
                doras = []
                liqi = [
                    False,
                    False,
                    False,
                    False,
                ]

                record_new_round = liqi_pb2.RecordNewRound()
                record_new_round.ParseFromString(wrapper.data)

                if 0 > record_new_round.chang or record_new_round.chang > 3:
                    raise RuntimeError(
                        f"uuid:{uuid} value error chang = {record_new_round.chang}"
                    )

                if 0 > record_new_round.ju or record_new_round.ju > 3:
                    raise RuntimeError(
                        f"uuid:{uuid} value error ju = {record_new_round.ju}"
                    )

                if 0 > record_new_round.ben or record_new_round.ben > 8:
                    raise RuntimeError(
                        f"uuid:{uuid} value error ben = {record_new_round.ben}"
                    )

                if 0 > record_new_round.liqibang or record_new_round.liqibang > 8:
                    raise RuntimeError(
                        f"uuid:{uuid} value error liqibang = {record_new_round.liqibang}"
                    )

                if len(record_new_round.doras) == 0:
                    raise RuntimeError(f"uuid:{uuid} value error doras == 0")

                if record_new_round.dora != "":
                    raise RuntimeError(
                        f"uuid:{uuid} value error dora = {record_new_round.dora}"
                    )

                seat_tiles = [
                    ["?"] * 13,
                    ["?"] * 13,
                    ["?"] * 13,
                    ["?"] * 13,
                ]

                hand_tile = getattr(record_new_round, f'tiles{id}')
                hand_tile = hand_tile[:13]

                for i, tile in enumerate(hand_tile):
                    seat_tiles[id][i] = _TILES2MJAI[tile]

                if record_new_round.doras[0] in _TILES2MJAI:
                    dora_marker = _TILES2MJAI[record_new_round.doras[0]]
                    doras.append(dora_marker)
                else:
                    raise RuntimeError(
                        f"uuid:{uuid} _TILES2MJAI without the {record_new_round.doras[0]} key."
                    )

                mjai_list.append({
                    "type": "start_kyoku",
                    "bakaze": _BAKAZE2MJAI[record_new_round.chang],
                    "kyoku": _KYOKU2MJAI[record_new_round.ju],
                    "honba": record_new_round.ben,
                    "kyotaku": record_new_round.liqibang,
                    "oya": record_new_round.ju % len(record_new_round.scores),
                    "scores": [score for score in record_new_round.scores],
                    "tehais": seat_tiles,
                    "dora_marker": dora_marker,
                })

                mo_tile = '?'
                mo_seat = -1

                for i in range(4):
                    hand_tile = getattr(record_new_round, f'tiles{i}')
                    if len(hand_tile) == 14:
                        mo_seat = i
                        if i == id:
                            mo_tile = _TILES2MJAI[hand_tile[13]]
                        break

                mjai_list.append({
                    "type": "tsumo",
                    "actor": mo_seat,
                    "pai": mo_tile,
                })
            elif wrapper.name == ".lq.RecordDealTile":
                record_deal_tile = liqi_pb2.RecordDealTile()
                record_deal_tile.ParseFromString(wrapper.data)

                mo_tile = '?'
                if record_deal_tile.seat == id:
                    if record_deal_tile.tile not in _TILES2MJAI:
                        raise RuntimeError(f"_TILES2MJAI without the {tile} key.")
                    mo_tile = _TILES2MJAI[record_deal_tile.tile]

                mjai_list.append({
                    "type": "tsumo",
                    "actor": record_deal_tile.seat,
                    "pai": mo_tile,
                })

                if len(record_deal_tile.doras) > len(doras):
                    for d_tile in record_deal_tile.doras[len(doras):]:
                        dora_marker = _TILES2MJAI[d_tile]
                        doras.append(dora_marker)
                        mjai_list.append({
                            "type": "dora",
                            "dora_marker": dora_marker
                        })
            elif wrapper.name == ".lq.RecordDiscardTile":
                record_discard_tile = liqi_pb2.RecordDiscardTile()
                record_discard_tile.ParseFromString(wrapper.data)

                if record_discard_tile.tile not in _TILES2MJAI:
                    raise RuntimeError(f"_TILES2MJAI without the {tile} key.")

                if record_discard_tile.is_liqi and (not liqi[record_discard_tile.seat]):
                    mjai_list.append({
                        "type": "reach",
                        "actor": record_discard_tile.seat
                    })

                ld_seat = record_discard_tile.seat
                mjai_list.append({
                    "type": "dahai",
                    "actor": record_discard_tile.seat,
                    "pai": _TILES2MJAI[record_discard_tile.tile],
                    "tsumogiri": record_discard_tile.moqie,
                })

                if record_discard_tile.is_liqi and (not liqi[record_discard_tile.seat]):
                    liqi[record_discard_tile.seat] = True
                    mjai_list.append({
                        "type": "reach_accepted",
                        "actor": record_discard_tile.seat,
                    })

                if len(record_discard_tile.doras) > len(doras):
                    for d_tile in record_discard_tile.doras[len(doras):]:
                        dora_marker = _TILES2MJAI[d_tile]
                        doras.append(dora_marker)
                        mjai_list.append({"type": "dora", "dora_marker": dora_marker})
            elif wrapper.name == ".lq.RecordChiPengGang":
                record_chi_peng_gang = liqi_pb2.RecordChiPengGang()
                record_chi_peng_gang.ParseFromString(wrapper.data)

                consumed = []
                pai = None
                for i, tiles in enumerate(record_chi_peng_gang.tiles):
                    if record_chi_peng_gang.froms[i] != record_chi_peng_gang.seat:
                        if pai:
                            raise RuntimeError(f"pai = {pai}")
                        pai = _TILES2MJAI[tiles]
                        continue
                    consumed.append(_TILES2MJAI[tiles])

                if record_chi_peng_gang.type == 0:
                    if len(record_chi_peng_gang.froms) != 3:
                        raise RuntimeError(f"value error {record_chi_peng_gang.froms} != 3")
                    mjai_list.append({
                        "type": "chi",
                        "actor": record_chi_peng_gang.seat,
                        "target": record_chi_peng_gang.froms[2],
                        "pai": pai,
                        "consumed": consumed,
                    })
                elif record_chi_peng_gang.type == 1:
                    if len(record_chi_peng_gang.froms) != 3:
                        raise RuntimeError(f"value error {record_chi_peng_gang.froms} != 3")
                    mjai_list.append({
                        "type": "pon",
                        "actor": record_chi_peng_gang.seat,
                        "target": record_chi_peng_gang.froms[2],
                        "pai": pai,
                        "consumed": consumed,
                    })
                elif record_chi_peng_gang.type == 2:
                    if len(record_chi_peng_gang.froms) != 4:
                        raise RuntimeError(f"value error {record_chi_peng_gang.froms} != 4")
                    mjai_list.append({
                        "type": "daiminkan",
                        "actor": record_chi_peng_gang.seat,
                        "target": record_chi_peng_gang.froms[3],
                        "pai": pai,
                        "consumed": consumed,
                    })
                else:
                    raise RuntimeError(f"unkown record_chi_peng_gang.type = {record_chi_peng_gang.type}")
            elif wrapper.name == ".lq.RecordAnGangAddGang":
                record_an_gang_add_gang = liqi_pb2.RecordAnGangAddGang()
                record_an_gang_add_gang.ParseFromString(wrapper.data)

                pai = _TILES2MJAI[record_an_gang_add_gang.tiles]
                if record_an_gang_add_gang.type == 2:
                    consumed = [pai] * 3
                    if pai == "5mr":
                        consumed = ["5m", "5m", "5m"]
                    elif pai == "5m":
                        consumed = ["5mr", pai, pai]
                    elif pai == "5pr":
                        consumed = ["5p", "5p", "5p"]
                    elif pai == "5p":
                        consumed = ["5pr", pai, pai]
                    elif pai == "5sr":
                        consumed = ["5s", "5s", "5s"]
                    elif pai == "5s":
                        consumed = ["5sr", pai, pai]
                    mjai_list.append({
                        "type": "kakan",
                        "actor": record_an_gang_add_gang.seat,
                        "pai": pai,
                        "consumed": consumed,
                        "can_act": record_an_gang_add_gang.seat == id,
                    })
                elif record_an_gang_add_gang.type == 3:
                    consumed = [pai] * 4
                    if pai == "5mr":
                        consumed = [pai, "5m", "5m", "5m"]
                    elif pai == "5m":
                        consumed = ["5mr", pai, pai, pai]
                    elif pai == "5pr":
                        consumed = [pai, "5p", "5p", "5p"]
                    elif pai == "5p":
                        consumed = ["5pr", pai, pai, pai]
                    elif pai == "5sr":
                        consumed = [pai, "5s", "5s", "5s"]
                    elif pai == "5s":
                        consumed = ["5sr", pai, pai, pai]
                    mjai_list.append({
                        "type": "ankan",
                        "actor": record_an_gang_add_gang.seat,
                        "consumed": consumed,
                        "can_act": record_an_gang_add_gang.seat == id,
                    })
                else:
                    raise RuntimeError(f"unkown record_an_gang_add_gang.type = {record_an_gang_add_gang.type}")
            elif wrapper.name == ".lq.RecordHule":
                record_hule = liqi_pb2.RecordHule()
                record_hule.ParseFromString(wrapper.data)

                for hule in record_hule.hules:
                    pai = _TILES2MJAI[hule.hu_tile]
                    hora = {
                        "type": "hora",
                        "actor": hule.seat,
                        "target": hule.seat,
                        "pai": pai,
                    }
                    if not hule.zimo:
                        hora["target"] = ld_seat
                    mjai_list.append(hora)
                    mjai_list.append({
                        "type": "end_kyoku",
                    })
            elif wrapper.name == ".lq.RecordNoTile":
                record_no_tile = liqi_pb2.RecordNoTile()
                record_no_tile.ParseFromString(wrapper.data)
                mjai_list.append({
                    "type": "ryukyoku",
                })
                mjai_list.append({
                    "type": "end_kyoku",
                })
            elif wrapper.name == ".lq.RecordLiuJu":
                record_liuJu = liqi_pb2.RecordLiuJu()
                record_liuJu.ParseFromString(wrapper.data)
                mjai_list.append({
                    "type": "ryukyoku",
                    "canAct": False,
                })
                mjai_list.append({
                    "type": "end_kyoku",
                })
            else:
                raise RuntimeError(f"Unresolved {wrapper.name}")
        return mjai_list
