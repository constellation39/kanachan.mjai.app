#!/usr/bin/env python3

import json
import pathlib
from collections import Counter
from typing import (
    Optional,
    List,
)

import torch

from constants import (
    _NUM2TILE,
    _TILE2NUM,
    _TILE_OFFSETS,
    _NUM2CHI,
    _CHI2NUM,
    _CHI_COUNTS,
    _CHI_TO_KUIKAE_TILES,
    _NUM2PENG,
    _PENG2NUM,
    _PENG_COUNTS,
    _PENG_TO_KUIKAE_TILE,
    _NUM2DAMINGGANG,
    _DAMINGGANG2NUM,
    _DAMINGGANG_COUNTS,
    _NUM2ANGANG,
    _ANGANG2NUM,
    _ANGANG_COUNTS,
    _JIAGANG_LIST,
    _NUM2JIAGANG,
    _JIAGANG_TO_PENG_LIST,
    _TILE34TILE37,
)
from kanachan.constants import (
    NUM_TYPES_OF_SPARSE_FEATURES,
    MAX_NUM_ACTIVE_SPARSE_FEATURES,
    NUM_TYPES_OF_PROGRESSION_FEATURES,
    MAX_LENGTH_OF_PROGRESSION_FEATURES,
    NUM_TYPES_OF_ACTIONS,
    MAX_NUM_ACTION_CANDIDATES,
)
from kanachan.model_loader import load_model

from hand_calculator import has_yihan, check_kokushi, calculate_shanten


class GameState:
    def __init__(
        self,
        *,
        my_name: str,
        room: int,
        game_style: int,
        my_grade: int,
        opponent_grade: int,
    ) -> None:
        self.__my_name = my_name
        self.__room = room
        self.__game_style = game_style
        self.__my_grade = my_grade
        self.__opponent_grade = opponent_grade
        self.__seat = None
        self.__player_grades = None
        self.__player_scores = None

    def on_new_game(self) -> None:
        pass

    def on_new_round(self, seat: int, scores: List[int]) -> None:
        self.__seat = seat

        self.__player_grades = [None] * 4
        for i in range(4):
            if i == self.__seat:
                self.__player_grades[i] = self.__my_grade
            else:
                self.__player_grades[i] = self.__opponent_grade

        self.__player_scores = list(scores)

    def __assert_initialized(self) -> None:
        if self.__player_grades is None:
            raise RuntimeError(
                "A method is called on a non-initialized `GameState` object."
            )
        assert self.__player_scores is not None

    def on_liqi_acceptance(self, seat: int) -> None:
        self.__assert_initialized()
        self.__player_scores[seat] -= 1000

    def get_my_name(self) -> str:
        # self.__assert_initialized()
        return self.__my_name

    def get_room(self) -> int:
        self.__assert_initialized()
        return self.__room

    def get_game_style(self) -> int:
        self.__assert_initialized()
        return self.__game_style

    def get_seat(self) -> int:
        self.__assert_initialized()
        return self.__seat

    def get_player_grade(self, seat: int) -> int:
        self.__assert_initialized()
        return self.__player_grades[seat]

    def get_player_rank(self, seat: int) -> int:
        self.__assert_initialized()

        score = self.__player_scores[seat]
        rank = 0
        for i in range(seat):
            if self.__player_scores[i] >= score:
                rank += 1
        for i in range(seat + 1, 4):
            if self.__player_scores[i] > score:
                rank += 1
        assert 0 <= rank and rank < 4
        return rank

    def get_player_score(self, seat: int) -> int:
        self.__assert_initialized()
        return self.__player_scores[seat]


class RoundState:
    def __init__(self) -> None:
        self.__chang = None
        self.__index = None
        self.__ben_chang = None
        self.__deposits = None
        self.__dora_indicators = None
        self.__num_left_tiles = None
        self.__my_hand = None
        self.__my_fulu_list = None
        self.__zimo_pai = None
        self.__my_first_zimo = None
        self.__liqi_to_be_accepted = None
        self.__my_liqi = None
        self.__my_lingshang_zimo = None
        self.__my_kuikae_tiles = None
        self.__my_zhenting = None
        self.__progression = None

    def on_new_round(
        self,
        chang: int,
        index: int,
        ben_chang: int,
        deposits: int,
        dora_indicator: int,
        hand: List[int],
    ) -> None:
        self.__chang = chang
        self.__index = index
        self.__ben_chang = ben_chang
        self.__deposits = deposits
        self.__dora_indicators = [dora_indicator]
        self.__num_left_tiles = 70
        self.__my_hand = hand
        self.__my_fulu_list = []
        self.__zimo_pai = None
        self.__my_first_zimo = True
        self.__liqi_to_be_accepted = [False, False, False, False]
        self.__my_liqi = False
        self.__my_lingshang_zimo = False
        self.__my_kuikae_tiles = []
        # self.__my_zhenting == 1: 非立直中の栄和拒否による一時的なフリテン
        # self.__my_zhenting == 2: 立直中の栄和拒否による永続的なフリテン
        self.__my_zhenting = 0
        self.__progression = [0]

    def get_chang(self) -> int:
        return self.__chang

    def get_index(self) -> int:
        return self.__index

    def get_num_ben_chang(self) -> int:
        return self.__ben_chang

    def get_num_deposits(self) -> int:
        return self.__deposits

    def get_dora_indicators(self) -> List[int]:
        return self.__dora_indicators

    def get_num_left_tiles(self) -> int:
        return self.__num_left_tiles

    def get_my_hand(self) -> List[int]:
        return self.__my_hand

    def get_my_fulu_list(self) -> List[int]:
        return self.__my_fulu_list

    def get_zimo_tile(self) -> Optional[int]:
        return self.__zimo_pai

    def is_in_liqi(self) -> bool:
        return self.__my_liqi

    def copy_progression(self) -> List[int]:
        return list(self.__progression)

    def __get_my_hand_counts(self) -> Counter:
        my_hand_counts = Counter()
        for tile in self.__my_hand:
            my_hand_counts[tile] += 1
        return my_hand_counts

    def __set_my_hand_counts(self, hand_counts: Counter) -> None:
        self.__my_hand = []
        for k, v in hand_counts.items():
            for i in range(v):
                self.__my_hand.append(k)
        self.__my_hand.sort()
        if len(self.__my_hand) not in (1, 2, 4, 5, 7, 8, 10, 11, 13):
            raise RuntimeError("An invalid hand.")

    def hand_to_34_array(self, hand: List[int]) -> List[int]:
        ans = [0] * 34
        for t in hand:
            if t < 30:
                ans[(t // 10) * 9 + (((t % 10) - 1) if (t % 10 != 0) else 4)] += 1
            else:
                ans[t - 3] += 1
        return ans

    def on_zimo(
        self, seat: int, mine: bool, tile: Optional[int], my_score: int
    ) -> Optional[List[int]]:
        if self.__zimo_pai is not None:
            raise AssertionError(f"self.__zimo_pai = {self.__zimo_pai}")

        self.__num_left_tiles -= 1
        self.__my_kuikae_tiles = []

        if not mine:
            if tile is not None:
                raise ValueError(f"tile = {tile}")
            return None

        if tile is None:
            raise ValueError("TODO: (A suitable error message)")
        self.__zimo_pai = tile

        # 非立直中の栄和拒否による一時的なフリテンを解消する．
        if self.__my_zhenting == 1:
            self.__my_zhenting = 0

        candidates = []

        if self.__my_liqi:
            # 立直中の場合．自摸切りを候補に追加する．
            candidates.append(self.__zimo_pai * 4 + 1 * 2 + 0)
        else:
            # 以下，立直中でない場合．
            # 手出しを候補として追加する．
            for i in range(len(self.__my_hand)):
                tile = self.__my_hand[i]
                candidates.append(tile * 4 + 0 * 2 + 0)
                new_hand = list(self.__my_hand)
                new_hand[i] = self.__zimo_pai
                if len(self.__my_fulu_list) == 0 and my_score >= 1000:
                    # If add a tile can make its shanten==-1, then it is riichiable.
                    for i in range(34):
                        array34 = self.hand_to_34_array(new_hand)
                        array34[i] += 1
                        if calculate_shanten(array34) == -1:
                            # 立直宣言を伴う手出しを候補として追加する．
                            candidates.append(tile * 4 + 0 * 2 + 1)
                            break

            # 自摸切りを候補として追加する．
            candidates.append(self.__zimo_pai * 4 + 1 * 2 + 0)
            if len(self.__my_fulu_list) == 0 and my_score >= 1000:
                # If add a tile can make its shanten==0, then it is riichiable.
                for i in range(34):
                    array34 = self.hand_to_34_array(self.__my_hand)
                    array34[i] += 1
                    if calculate_shanten(array34) == -1:
                        # 立直宣言を伴う自摸切りを候補として追加する．
                        candidates.append(tile * 4 + 1 * 2 + 1)
                        break

        combined_hand = self.__my_hand + [self.__zimo_pai]

        # 暗槓が候補として追加できるかどうかをチェックする．
        counts = Counter()
        for p in combined_hand:
            if p == 0:
                counts[4] += 1
            elif 1 <= p <= 9:
                counts[p - 1] += 1
            elif p == 10:
                counts[13] += 1
            elif 11 <= p <= 19:
                counts[p - 2] += 1
            elif p == 20:
                counts[22] += 1
            elif 21 <= p:
                assert p < 37
                counts[p - 3] += 1
        for k, v in counts.items():
            # 立直中の送り槓を禁止する．
            if self.is_in_liqi():
                p = self.__zimo_pai
                if p == 0:
                    c = 4
                elif 1 <= p <= 9:
                    c = p - 1
                elif p == 10:
                    c = 13
                elif 11 <= p <= 19:
                    c = p - 2
                elif p == 20:
                    c = 22
                elif 21 <= p:
                    assert p < 37
                    c = p - 3
                if k == c:
                    continue
            if v >= 4:
                candidates.append(148 + k)

        # 加槓が候補として追加できるかどうかをチェックする．
        peng_list = []
        for fulu in self.__my_fulu_list:
            if 312 <= fulu and fulu <= 431:
                peng = (fulu - 312) % 40
                peng_list.append(peng)
        for peng, t in enumerate(_JIAGANG_LIST):
            if peng in peng_list and t in combined_hand:
                candidates.append(182 + t)

        # 自摸和が候補として追加できるかどうかをチェックする．
        if calculate_shanten(self.hand_to_34_array(combined_hand)) == -1:
            player_wind = (seat + 4 - self.__index) % 4
            yihan = has_yihan(
                self.__chang,
                player_wind,
                self.__my_hand,
                self.__my_fulu_list,
                self.__zimo_pai,
                rong=False,
            )
            if (
                self.__my_liqi
                or self.__num_left_tiles == 0
                or self.__my_lingshang_zimo
                or yihan
            ):
                candidates.append(219)

        if self.__my_first_zimo:
            assert not self.__my_liqi
            # 九種九牌が候補として追加できるかどうかをチェックする．
            count = 0
            for p in set(combined_hand):
                if p in (1, 9, 11, 19, 21, 29, 30, 31, 32, 33, 34, 35, 36):
                    count += 1
            if count >= 9:
                candidates.append(220)

        self.__my_first_zimo = False
        self.__my_lingshang_zimo = False

        candidates = list(set(candidates))
        candidates.sort()
        return candidates

    def __get_my_zhenting_tiles(self, seat: int) -> List[int]:
        # 自分が捨てた牌を列挙する．
        discarded_tiles = set()
        for p in self.__progression:
            if p < 5 or 596 < p:
                continue
            encode = p - 5
            actor = encode // 148
            encode = encode % 148
            tile = encode // 4
            if actor != seat:
                continue
            discarded_tiles.add(tile)

        # 和牌の候補を列挙する．
        hupai_candidates = []
        for i in range(37):
            combined_hand = self.__my_hand + [i]
            if calculate_shanten(self.hand_to_34_array(combined_hand)) == -1:
                hupai_candidates.append(i)

        # 和牌の候補の中に自分が捨てた牌が1つでも含まれているならば，
        # 和牌の候補全てがフリテンの対象でありロンできない．
        for hupai_candidate in hupai_candidates:
            if hupai_candidate in discarded_tiles:
                return hupai_candidates
        return []

    def on_dapai(
        self, seat: int, actor: int, tile: int, moqi: bool
    ) -> Optional[List[int]]:
        if self.__num_left_tiles == 69:
            # 雀魂から学習したモデルは親の第1打牌が必ず手出しになる．
            moqi = False

        liqi = self.__liqi_to_be_accepted[seat]

        encode = 5 + actor * 148 + tile * 4 + (2 if moqi else 0) + (1 if liqi else 0)
        self.__progression.append(encode)

        if actor == seat:
            if moqi:
                if self.__zimo_pai is None:
                    raise RuntimeError("TODO: (A suitable error message)")
                if self.__zimo_pai != tile:
                    raise RuntimeError("TODO: (A suitable error message)")
                self.__zimo_pai = None
                return None
            index = None
            for i in range(len(self.__my_hand)):
                if self.__my_hand[i] == tile:
                    index = i
                    break
            if index is None:
                # 自分が親の時の第1打牌で自摸切りの場合．
                if self.__num_left_tiles != 69:
                    raise RuntimeError("TODO: (A suitable error message)")
                if self.__zimo_pai is None:
                    raise RuntimeError("TODO: (A suitable error message)")
                if self.__zimo_pai != tile:
                    raise RuntimeError("TODO: (A suitable error message)")
                self.__zimo_pai = None
                return None
            self.__my_hand.pop(index)
            if self.__zimo_pai is not None:
                self.__my_hand.append(self.__zimo_pai)
                self.__zimo_pai = None
                self.__my_hand.sort()
            assert len(self.__my_hand) in (1, 4, 7, 10, 13)
            return None

        relseat = (actor + 4 - seat) % 4 - 1

        skippable = False

        hand_counts = self.__get_my_hand_counts()

        candidates = []

        if not self.__my_liqi and relseat == 2 and self.__num_left_tiles > 0:
            # チーができるかどうかチェックする．
            # 河底牌に対するチーが可能かどうか確認する．
            for i, (t, consumed_counts) in enumerate(_CHI_COUNTS):
                if tile != t:
                    continue
                new_hand_counts = Counter(hand_counts)
                for k, v in consumed_counts.items():
                    if hand_counts[k] < v:
                        new_hand_counts = None
                        break
                    new_hand_counts[k] -= v
                if new_hand_counts is not None:
                    # チーの後に食い替えによって打牌が禁止される牌のみが
                    # 残る場合は，そのようなチー自体が禁止される．
                    # 以下では，そのようなチーを候補から除去している．
                    for kuikae_tile in _CHI_TO_KUIKAE_TILES[i]:
                        new_hand_counts[kuikae_tile] = 0
                    flag = False
                    for count in new_hand_counts.values():
                        if count >= 1:
                            flag = True
                            break
                    if flag:
                        self.__my_kuikae_tiles = list(_CHI_TO_KUIKAE_TILES[i])
                        candidates.append(222 + i)
                        skippable = True

        if not self.__my_liqi and self.__num_left_tiles > 0:
            # ポンができるかどうかチェックする．
            # 河底牌に対するポンが可能かどうか確認する．
            for i, (t, consumed_counts) in enumerate(_PENG_COUNTS):
                if tile != t:
                    continue
                new_hand_counts = Counter(hand_counts)
                for k, v in consumed_counts.items():
                    if hand_counts[k] < v:
                        new_hand_counts = None
                        break
                    new_hand_counts[k] -= v
                if new_hand_counts is not None:
                    # ポンの後に食い替えによって打牌が禁止される牌のみが
                    # 残る場合は，そのようなポン自体が禁止される．
                    # 以下では，そのようなポンを候補から除去している．
                    new_hand_counts[_PENG_TO_KUIKAE_TILE[i]] = 0
                    flag = False
                    for count in new_hand_counts.values():
                        if count >= 1:
                            flag = True
                            break
                    if flag:
                        self.__my_kuikae_tiles = [_PENG_TO_KUIKAE_TILE[i]]
                        candidates.append(312 + relseat * 40 + i)
                        skippable = True

        if not self.__my_liqi:
            # 大明槓ができるかどうかチェックする．
            # 河底牌に対する大明槓が可能かどうか確認する．
            if self.__num_left_tiles > 0:
                for t, consumed_counts in enumerate(_DAMINGGANG_COUNTS):
                    if tile != t:
                        continue
                    flag = True
                    for k, v in consumed_counts.items():
                        if hand_counts[k] < v:
                            flag = False
                            break
                    if flag:
                        candidates.append(432 + relseat * 37 + t)
                        skippable = True

        combined_hand = self.__my_hand + [tile]

        xiangting_number = calculate_shanten(self.hand_to_34_array(combined_hand))
        if (
            xiangting_number == -1
            and (tile not in self.__get_my_zhenting_tiles(seat))
            and self.__my_zhenting == 0
        ):
            # ロンが出来るかどうかチェックする．
            player_wind = (seat + 4 - self.__index) % 4
            yihan = has_yihan(
                self.__chang,
                player_wind,
                self.__my_hand,
                self.__my_fulu_list,
                tile,
                rong=True,
            )
            if self.__my_liqi or self.__num_left_tiles == 0 or yihan:
                candidates.append(543 + relseat)
                skippable = True

        if skippable:
            candidates.append(221)

        candidates.sort()
        return candidates if len(candidates) > 0 else None

    def on_chi(self, mine: bool, seat: int, chi: int) -> Optional[List[int]]:
        self.__my_first_zimo = False
        self.__progression.append(597 + seat * 90 + chi)

        if not mine:
            self.__my_kuikae_tiles = []
            return None

        my_hand_counts = self.__get_my_hand_counts()
        consumed_counts = _CHI_COUNTS[chi][1]
        for k, v in consumed_counts.items():
            if my_hand_counts[k] < v:
                raise RuntimeError("An invalid chi.")
            my_hand_counts[k] -= v
        self.__set_my_hand_counts(my_hand_counts)

        if len(self.__my_fulu_list) == 4:
            raise RuntimeError("An invalid chi.")
        self.__my_fulu_list.append(222 + chi)

        candidates = []
        for tile in self.__my_hand:
            if tile not in self.__my_kuikae_tiles:
                candidates.append(tile * 4 + 0 * 2 + 0)
        self.__my_kuikae_tiles = []
        return list(set(candidates))

    def on_peng(
        self, mine: bool, seat: int, relseat: int, peng: int
    ) -> Optional[List[int]]:
        self.__my_first_zimo = False
        self.__progression.append(957 + seat * 120 + relseat * 40 + peng)

        if not mine:
            self.__my_kuikae_tiles = []
            return None

        my_hand_counts = self.__get_my_hand_counts()
        consumed_counts = _PENG_COUNTS[peng][1]
        for k, v in consumed_counts.items():
            if my_hand_counts[k] < v:
                raise RuntimeError("An invalid peng.")
            my_hand_counts[k] -= v
        self.__set_my_hand_counts(my_hand_counts)

        if len(self.__my_fulu_list) == 4:
            raise RuntimeError("An invalid peng.")
        self.__my_fulu_list.append(312 + relseat * 40 + peng)

        candidates = []
        for tile in self.__my_hand:
            if tile not in self.__my_kuikae_tiles:
                candidates.append(tile * 4 + 0 * 2 + 0)
        self.__my_kuikae_tiles = []
        return list(set(candidates))

    def on_daminggang(
        self, mine: bool, seat: int, relseat: int, daminggang: int
    ) -> None:
        self.__my_first_zimo = False
        self.__my_kuikae_tiles = []
        self.__progression.append(1437 + seat * 111 + relseat * 37 + daminggang)

        if not mine:
            return

        my_hand_counts = self.__get_my_hand_counts()
        consumed_counts = _DAMINGGANG_COUNTS[daminggang]
        for k, v in consumed_counts.items():
            if my_hand_counts[k] < v:
                raise RuntimeError("An invalid daminggang.")
            my_hand_counts[k] -= v
        self.__set_my_hand_counts(my_hand_counts)

        if len(self.__my_fulu_list) == 4:
            raise RuntimeError("An invalid daminggang.")
        self.__my_fulu_list.append(432 + relseat * 37 + daminggang)

        self.__my_lingshang_zimo = True

    def on_angang(self, seat: int, actor: int, angang: int) -> Optional[List[int]]:
        self.__my_first_zimo = False
        self.__progression.append(1881 + actor * 34 + angang)

        if seat != actor:
            # 暗槓に対する国士無双の槍槓をチェックする．
            player_wind = (seat + 4 - self.__index) % 4
            can_ron_kokushi = check_kokushi(
                self.__chang,
                player_wind,
                self.__my_hand,
                self.__my_fulu_list,
                _TILE34TILE37[angang],
                rong=False,
            )
            if not can_ron_kokushi:
                return None

        if self.__zimo_pai is None:
            raise RuntimeError("TODO: (A suitable error message)")

        my_hand_counts = self.__get_my_hand_counts()
        my_hand_counts[self.__zimo_pai] += 1
        consumed_counts = _ANGANG_COUNTS[angang]
        for k, v in consumed_counts.items():
            if my_hand_counts[k] < v:
                raise RuntimeError("An invalid angang.")
            my_hand_counts[k] -= v
        self.__set_my_hand_counts(my_hand_counts)
        self.__zimo_pai = None

        if len(self.__my_fulu_list) == 4:
            raise RuntimeError("An invalid angang.")
        self.__my_fulu_list.append(148 + angang)

        self.__my_lingshang_zimo = True

        return None

    def on_jiagang(self, seat: int, actor: int, tile: int) -> Optional[List[int]]:
        self.__my_first_zimo = False
        self.__progression.append(2017 + seat * 37 + tile)

        if seat != actor:
            # 槍槓が可能かどうかをチェックする．
            combined_hand = self.__my_hand + [tile]
            xiangting_number = calculate_shanten(self.hand_to_34_array(combined_hand))
            if xiangting_number == -1:
                relseat = (actor + 4 - seat) % 4 - 1
                return [221, 543 + relseat]
            return None

        if self.__zimo_pai is None:
            raise RuntimeError("TODO: A suitable error message")

        index = None
        for i in range(len(self.__my_hand)):
            if self.__my_hand[i] == tile:
                index = i
                break
        if index is not None:
            self.__my_hand.pop(index)
            self.__my_hand.append(self.__zimo_pai)
            self.__zimo_pai = None
            self.__my_hand.sort()
        else:
            if self.__zimo_pai != tile:
                raise RuntimeError("TODO: A suitable error message")
            self.__zimo_pai = None

        index = None
        for i in range(len(self.__my_fulu_list)):
            # 加槓の対象となるポンを探す．
            fulu = self.__my_fulu_list[i]
            if fulu < 312 or 431 < fulu:
                # ポンではない．
                continue
            peng = (fulu - 312) % 40
            if peng in _JIAGANG_TO_PENG_LIST[tile]:
                index = i
                break
        if index is None:
            raise RuntimeError("TODO: (A suitable error message)")
        self.__my_fulu_list[index] = (
            _PENG_TO_KUIKAE_TILE[(self.__my_fulu_list[index] - 312) % 40] + 182
        )

        self.__my_lingshang_zimo = True

        return None

    def on_liqi(self, seat: int) -> None:
        if any(self.__liqi_to_be_accepted):
            raise RuntimeError("TODO: (A suitable error message)")
        self.__liqi_to_be_accepted[seat] = True

    def on_liqi_acceptance(self, mine: bool, seat: int) -> None:
        self.__deposits += 1

        if not self.__liqi_to_be_accepted[seat]:
            raise RuntimeError("TODO: (A suitable error message)")
        self.__liqi_to_be_accepted[seat] = False

        if mine:
            self.__my_liqi = True

    def on_new_dora(self, tile: int) -> None:
        if len(self.__dora_indicators) >= 5:
            raise RuntimeError(self.__dora_indicators)
        self.__dora_indicators.append(tile)

    def set_zhenting(self, zhenting: int) -> None:
        if zhenting not in (1, 2):
            raise ValueError("TODO: (A suitable error message)")
        self.__my_zhenting = zhenting


class Kanachan:
    def __init__(
        self,
        # model_path=f"{pathlib.Path(__file__).parent}/model/model.kanachan",
        model_path=f"{pathlib.Path(__file__).parent}/model/model.400000.kanachan",
    ) -> None:
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.device = "cpu"
        self.__model = load_model(model_path, map_location=self.device)
        self.__model.to(device=self.device, dtype=torch.float32)
        self.__model.eval()

        with open(f"{pathlib.Path(__file__).parent}/game.json", encoding="UTF-8") as f:
            game_config = json.load(f)
            self.__game_state = GameState(
                my_name=game_config["my_name"],
                room=game_config["room"],
                game_style=game_config["game_style"],
                my_grade=game_config["my_grade"],
                opponent_grade=game_config["opponent_grade"],
            )
        self.__round_state = RoundState()

    def __on_hello(self, message: dict) -> dict:
        assert message["type"] == "hello"

        # if 'can_act' not in message:
        #     raise RuntimeError('A `hello` message without the `can_act` key.')
        # can_act = message['can_act']
        # if not can_act:
        #     raise RuntimeError(
        #         f'A `hello` message with an invalid `can_act` (can_act = {can_act}).')

        my_name = self.__game_state.get_my_name()
        return {"type": "join", "name": my_name, "room": "default"}

    def __on_start_game(self, message: dict) -> dict:
        assert message["type"] == "start_game"

        # 2022/10/06 時点でのAI雀荘の実装では， `start_game` メッセージに
        # `id` キーが伴わないように推定されるので，この時点では `seat` を
        # 設定できない．
        #
        # if 'id' not in message:
        #    raise RuntimeError('A `start_game` message without the `id` key.')
        # seat = message['id']
        # if seat < 0 or 4 <= seat:
        #    raise RuntimeError(
        #        f'A `start_game` message with an invalid `id` (id = {seat}).')
        # self.__game_state.on_new_game(seat)

        self.__game_state.on_new_game()

        return {"type": "none"}

    def __on_start_kyoku(self, message: dict) -> None:
        assert message["type"] == "start_kyoku"

        if "bakaze" not in message:
            raise RuntimeError("A `start_kyoku` message without the `bakaze` key.")
        chang = message["bakaze"]
        if chang not in ("E", "S", "W"):
            raise RuntimeError(
                f"A `start_kyoku` message with an invalid `bakaze` (bakaze = {chang})."
            )
        chang = {"E": 0, "S": 1, "W": 2}[chang]

        if "kyoku" not in message:
            raise RuntimeError("A `start_kyoku` message without the `kyoku` key.")
        round_index = message["kyoku"]
        if round_index < 1 or 4 < round_index:
            raise RuntimeError(
                f"A `start_kyoku` message with an invalid `kyoku` (kyoku = {round_index})."
            )
        round_index -= 1

        if "honba" not in message:
            raise RuntimeError("A `start_kyoku` message without the `honba` key.")
        ben_chang = message["honba"]
        if ben_chang < 0:
            raise RuntimeError(
                f"A `start_kyoku` message with an invalid `honba` (honba = {ben_chang})."
            )

        if "kyotaku" not in message:
            raise RuntimeError("A `start_kyoku` message without the `kyotaku` key.")
        deposits = message["kyotaku"]
        if deposits < 0:
            raise RuntimeError(
                f"A `start_kyoku` message with an invalid `kyotaku` (kyotaku = {deposits})."
            )

        if "oya" not in message:
            raise RuntimeError("A `start_kyoku` message without the `oya` key.")
        dealer = message["oya"]
        if dealer != round_index:
            raise RuntimeError(
                f"An inconsistent `start_kyoku` message (round_index = {round_index}, oya = {dealer})."
            )

        if "dora_marker" not in message:
            raise RuntimeError("A `start_kyoku` message without the `dora_marker` key.")
        dora_indicator = message["dora_marker"]
        if dora_indicator not in _TILE2NUM:
            raise RuntimeError(
                "A `start_kyoku` message with an invalid `dora_marker` (dora_marker = {dora_indicator})."
            )
        dora_indicator = _TILE2NUM[dora_indicator]

        if "scores" not in message:
            raise RuntimeError("A `start_kyoku` message without the `scores` key.")
        scores = message["scores"]
        if len(scores) != 4:
            raise RuntimeError(
                f"A `start_kyoku` message with an invalid scores (length = {len(scores)})."
            )

        if "tehais" not in message:
            raise RuntimeError("A `start_kyoku` message without the `tehais` key.")
        hands = message["tehais"]
        if len(hands) != 4:
            raise RuntimeError(
                f"A `start_kyoku` message with an wrong `tehais` (length = {len(hands)})."
            )

        # 2022/10/06 時点でのAI雀荘の実装では， `start_game` メッセージに
        # `id` キーが伴わないように推定されるので，その時点では `seat` を
        # 設定できない．以下は workaround
        seat = None
        for i in range(4):
            if hands[i][0] != "?":
                if seat is not None:
                    raise RuntimeError("TODO: (A suitable error message)")
                seat = i
        if seat is None:
            raise RuntimeError("TODO: (A suitable error message)")

        for i, hand in enumerate(hands):
            if i != seat:
                if hand != [
                    "?",
                    "?",
                    "?",
                    "?",
                    "?",
                    "?",
                    "?",
                    "?",
                    "?",
                    "?",
                    "?",
                    "?",
                    "?",
                ]:
                    raise RuntimeError(
                        f"A `start_kyoku` message with an wrong `tehais` (seat = {seat}, i = {i}, hand = {hand})."
                    )
            else:
                if len(hand) != 13:
                    raise RuntimeError(
                        f"A `start_kyoku` message with an wrong `tehais` (seat = {seat}, hand = {hand})."
                    )
                for i in range(13):
                    if hand[i] not in _TILE2NUM:
                        raise RuntimeError(
                            f"A `start_kyoku` message with an wrong `tehais` (seat = {seat}, hand = {hand})."
                        )
                    hand[i] = _TILE2NUM[hand[i]]
        hand = hands[seat]

        self.__game_state.on_new_round(seat, scores)
        self.__round_state.on_new_round(
            chang, round_index, ben_chang, deposits, dora_indicator, hand
        )

    def __respond(self, dapai: Optional[int], candidates: List[int]) -> dict:
        seat = self.__game_state.get_seat()

        sparse = []
        # Room [0 ~ 4]
        sparse.append(self.__game_state.get_room())

        # Game Style [5 ~ 6]
        sparse.append(self.__game_state.get_game_style() + 5)

        # Player Grade0 [7 ~ 22]
        sparse.append(self.__game_state.get_player_grade(0) + 7)

        # Player Grade1 [23 ~ 38]
        sparse.append(self.__game_state.get_player_grade(1) + 23)

        # Player Grade2 [39 ~ 54]
        sparse.append(self.__game_state.get_player_grade(2) + 39)

        # Player Grade3 [55 ~ 70]
        sparse.append(self.__game_state.get_player_grade(3) + 55)

        # Seat [71 ~ 74]
        sparse.append(seat + 71)

        # Game Wind [75 ~ 77]
        sparse.append(self.__round_state.get_chang() + 75)

        # Round [78 ~ 81]
        sparse.append(self.__round_state.get_index() + 78)

        # of Left Tiles to Draw [82 ~ 151]
        sparse.append(self.__round_state.get_num_left_tiles() + 82)

        # Dora Indicator 152
        for i, dora_indicator in enumerate(self.__round_state.get_dora_indicators()):
            sparse.append(dora_indicator + 37 * i + 152)

        # Hand [337 ~ 472]
        hand_encode = [None] * 136
        for tile in self.__round_state.get_my_hand():
            flag = False
            for i in range(_TILE_OFFSETS[tile], _TILE_OFFSETS[tile + 1]):
                if hand_encode[i] is None:
                    hand_encode[i] = 1
                    flag = True
                    break
            if not flag:
                raise RuntimeError("TODO: (A suitable error message)")

        for i in range(136):
            if hand_encode[i] == 1:
                sparse.append(i + 337)

        zimo_tile = self.__round_state.get_zimo_tile()
        if zimo_tile is not None:
            sparse.append(zimo_tile + 473)

        for i in range(len(sparse), MAX_NUM_ACTIVE_SPARSE_FEATURES):
            sparse.append(NUM_TYPES_OF_SPARSE_FEATURES)
        sparse = torch.tensor(sparse, device="cpu", dtype=torch.int32).unsqueeze(0)

        numeric = []
        numeric.append(self.__round_state.get_num_ben_chang())
        numeric.append(self.__round_state.get_num_deposits())

        for i in range(4):
            player_score = self.__game_state.get_player_score(0)
            if player_score is not None:
                numeric.append(player_score / 10000.0)
            else:
                numeric.append(0.0)
        numeric = torch.tensor(numeric, device="cpu", dtype=torch.float32).unsqueeze(0)

        progression = self.__round_state.copy_progression()
        for i in range(len(progression), MAX_LENGTH_OF_PROGRESSION_FEATURES):
            progression.append(NUM_TYPES_OF_PROGRESSION_FEATURES)
        progression = torch.tensor(
            progression, device="cpu", dtype=torch.int32
        ).unsqueeze(0)

        candidates_ = list(candidates)
        for i in range(len(candidates_), MAX_NUM_ACTION_CANDIDATES):
            candidates_.append(NUM_TYPES_OF_ACTIONS)
        candidates_ = torch.tensor(
            candidates_, device="cpu", dtype=torch.int32
        ).unsqueeze(0)

        with torch.no_grad():
            progression = self.__model(sparse, numeric, progression, candidates_)
            if len(progression) == 3:
                action = progression[2].squeeze(dim=0).item()

                decode = progression[1]
                decode = decode.squeeze(dim=0)
                decode = decode[: len(candidates)]

                min_value = torch.min(decode)
                shifted_tensor_data = decode - min_value

                sum_of_elements = torch.sum(shifted_tensor_data)
                proportions = shifted_tensor_data / sum_of_elements

                print("Elements: ", end="")
                for i, element in enumerate(proportions):
                    if i == action:
                        print(f"{i}: [{element.item():.2f}] ", end="")
                    else:
                        print(f"{i}: {element.item():.2f} ", end="")
                print()

            elif len(progression) == 4:
                action = progression[3].squeeze(dim=0).item()

                decode = progression[2]
                decode = decode.squeeze(dim=0)
                decode = decode[: len(candidates)]

                min_value = torch.min(decode)
                shifted_tensor_data = decode - min_value

                sum_of_elements = torch.sum(shifted_tensor_data)
                proportions = shifted_tensor_data / sum_of_elements

                print("Elements: ", end="")
                for i, element in enumerate(proportions):
                    if i == action:
                        print(f"{i}: [{element.item():.2f}] ", end="")
                    else:
                        print(f"{i}: {element.item():.2f} ", end="")
                print()

            else:
                raise ValueError()
        candidates_ = torch.squeeze(candidates_, dim=0)
        decision = candidates_[action].item()

        if 0 <= decision and decision <= 147:
            tile = decision // 4
            tile = _NUM2TILE[tile]
            encode = decision % 4
            moqi = encode // 2 == 1
            encode = encode % 2
            liqi = encode == 1

            if liqi:
                return {"type": "reach", "actor": seat}
            return {"type": "dahai", "actor": seat, "pai": tile, "tsumogiri": moqi}

        if 148 <= decision and decision <= 181:
            angang = _NUM2ANGANG[decision - 148]
            return {"type": "ankan", "actor": seat, "consumed": angang}

        if 182 <= decision and decision <= 218:
            tile, consumed = _NUM2JIAGANG[decision - 182]
            return {"type": "kakan", "actor": seat, "pai": tile, "consumed": consumed}

        if decision == 219:
            hupai = self.__round_state.get_zimo_tile()
            if hupai is None:
                raise RuntimeError("Trying zimohu without any zimo tile.")
            hupai = _NUM2TILE[hupai]
            return {"type": "hora", "actor": seat, "target": seat, "pai": hupai}

        if decision == 220:
            return {"type": "ryukyoku"}

        if decision == 221:
            in_liqi = self.__round_state.is_in_liqi()
            for i in (543, 544, 545):
                if i in candidates:
                    # 栄和が選択肢にあるにも関わらず見逃しを選択した．
                    # この結果，フリテンが発生する．
                    self.__round_state.set_zhenting(2 if in_liqi else 1)
                    break
            return {"type": "none"}

        if 222 <= decision and decision <= 311:
            tile, consumed = _NUM2CHI[decision - 222]
            return {
                "type": "chi",
                "actor": seat,
                "target": (seat + 3) % 4,
                "pai": tile,
                "consumed": consumed,
            }

        if 312 <= decision and decision <= 431:
            encode = decision - 312
            relseat = encode // 40
            target = (seat + relseat + 1) % 4
            encode = encode % 40
            tile, consumed = _NUM2PENG[encode]
            return {
                "type": "pon",
                "actor": seat,
                "target": target,
                "pai": tile,
                "consumed": consumed,
            }

        if 432 <= decision and decision <= 542:
            encode = decision - 432
            relseat = encode // 37
            target = (seat + relseat + 1) % 4
            encode = encode % 37
            tile, consumed = _NUM2DAMINGGANG[encode]
            return {
                "type": "daiminkan",
                "actor": seat,
                "target": target,
                "pai": tile,
                "consumed": consumed,
            }

        if 543 <= decision and decision <= 545:
            relseat = decision - 543
            target = (seat + relseat + 1) % 4
            hupai = dapai
            if hupai is None:
                raise RuntimeError("Trying rong without any dapai.")
            hupai = _NUM2TILE[hupai]
            return {"type": "hora", "actor": seat, "target": target, "pai": hupai}

        raise RuntimeError(f"An invalid decision (decision = {decision}).")

    def __on_zimo(self, message: dict) -> dict:
        assert message["type"] == "tsumo"

        seat = self.__game_state.get_seat()

        if "actor" not in message:
            raise RuntimeError("A `tsumo` message without the `actor` key.")
        actor = message["actor"]
        if actor < 0 or 4 <= actor:
            raise RuntimeError(
                f"A `tsumo` message with an invalid `actor` (actor = {actor})."
            )
        mine = actor == seat

        if "pai" not in message:
            raise RuntimeError("A `tsumo` message without the `pai` key.")
        tile = message["pai"]

        my_score = self.__game_state.get_player_score(seat)

        if not mine:
            if tile != "?":
                raise RuntimeError(
                    f"An inconsistent `tsumo` message (seat = {seat}, actor = {actor}, pai = {tile})."
                )
            self.__round_state.on_zimo(seat, mine, None, my_score)
        else:
            if tile not in _TILE2NUM:
                raise RuntimeError(
                    f"A `tsumo` message with an invalid `pai` (seat = {seat}, actor = {actor}, pai = {tile})."
                )
            tile = _TILE2NUM[tile]
            candidates = self.__round_state.on_zimo(seat, mine, tile, my_score)
            if not isinstance(candidates, list):
                raise RuntimeError(candidates)
            if len(candidates) == 0:
                raise RuntimeError("The length of `candidates` is equal to 0.")
            return self.__respond(None, candidates)

    def __on_dapai(self, message: dict) -> dict:
        assert message["type"] == "dahai"

        seat = self.__game_state.get_seat()

        if "actor" not in message:
            raise RuntimeError("A `dahai` message without the `actor` key.")
        actor = message["actor"]
        if actor < 0 or 4 <= actor:
            raise RuntimeError(
                f"A `dahai` message with an invalid `actor` (actor = {actor})."
            )

        if "pai" not in message:
            raise RuntimeError("A `dahai` message without the `pai` key.")
        tile = message["pai"]
        if tile not in _TILE2NUM:
            raise RuntimeError(
                f"A `dahai` message with an invalid `pai` (pai = {tile})."
            )
        tile = _TILE2NUM[tile]

        if "tsumogiri" not in message:
            raise RuntimeError("A `dahai` message without the `tsumogiri` key.")
        moqi = message["tsumogiri"]

        candidates = self.__round_state.on_dapai(seat, actor, tile, moqi)

        if actor == seat:
            # 自身の打牌に対してやることは何もない．
            if candidates is not None:
                raise RuntimeError(candidates)
            return

        if candidates is None:
            return

        if not isinstance(candidates, list):
            raise RuntimeError(candidates)
        if len(candidates) < 2:
            raise RuntimeError(candidates)
        return self.__respond(tile, candidates)

    def __on_chi(self, message: dict) -> dict:
        assert message["type"] == "chi"

        if "actor" not in message:
            raise RuntimeError("A `chi` message without the `actor` key.")
        actor = message["actor"]
        if actor < 0 or 4 <= actor:
            raise RuntimeError(
                f"A `chi` message with an invalid `actor` (actor = {actor})."
            )
        mine = actor == self.__game_state.get_seat()

        if "target" not in message:
            raise RuntimeError("A `chi` message without the `target` key.")
        target = message["target"]
        if target < 0 or 4 <= target:
            raise RuntimeError(
                f"A `chi` message with an invalid `target` (target = {target})."
            )
        if (target + 4 - actor) % 4 != 3:
            raise RuntimeError(
                f"An inconsistent `chi` message (actor = {actor}, target = {target})."
            )

        if "pai" not in message:
            raise RuntimeError("A `chi` message without the `pai` key.")
        tile = message["pai"]
        if tile not in _TILE2NUM:
            raise RuntimeError(f"A `chi` message with an invalid `pai` (pai = {tile}).")

        if "consumed" not in message:
            raise RuntimeError("A `pon` message without the `consumed` key.")
        consumed = message["consumed"]
        for t in consumed:
            if t not in _TILE2NUM:
                raise RuntimeError(
                    f"A `chi` message with an invalid `consumed` (consumed = {consumed})."
                )

        chi = (tile, tuple(consumed))
        if chi not in _CHI2NUM:
            raise RuntimeError(chi)
        chi = _CHI2NUM[chi]

        candidates = self.__round_state.on_chi(mine, actor, chi)

        if candidates is None:
            if mine:
                raise RuntimeError("TODO: (A suitable error message)")
            return

        if not isinstance(candidates, list):
            raise RuntimeError(candidates)
        if len(candidates) == 0:
            raise RuntimeError("TODO: (A suitable error message)")
        if not mine:
            raise RuntimeError("TODO: (A suitable error message)")
        return self.__respond(None, candidates)

    def __on_peng(self, message: dict) -> dict:
        assert message["type"] == "pon"

        if "actor" not in message:
            raise RuntimeError("A `pon` message without the `actor` key.")
        actor = message["actor"]
        if actor < 0 or 4 <= actor:
            raise RuntimeError(
                f"A `pon` message with an invalid `actor` (actor = {actor})."
            )
        mine = actor == self.__game_state.get_seat()

        if "target" not in message:
            raise RuntimeError("A `pon` message without the `target` key.")
        target = message["target"]
        if target < 0 or 4 <= target:
            raise RuntimeError(
                f"A `pon` message with an invalid `target` (target = {target})."
            )
        if actor == target:
            raise RuntimeError(
                f"An inconsistent `pon` message (actor = {actor}, target = {target})."
            )
        relseat = (target + 4 - actor) % 4 - 1

        if "pai" not in message:
            raise RuntimeError("A `pon` message without the `pai` key.")
        tile = message["pai"]
        if tile not in _TILE2NUM:
            raise RuntimeError(f"A `pon` message with an invalid `pai` (pai = {tile}).")

        if "consumed" not in message:
            raise RuntimeError("A `pon` message without the `consumed` key.")
        consumed = message["consumed"]
        for t in consumed:
            if t not in _TILE2NUM:
                raise RuntimeError(
                    f"A `pon` message with an invalid `consumed` (consumed = {consumed})."
                )

        peng = (tile, tuple(consumed))
        if peng not in _PENG2NUM:
            raise RuntimeError(peng)
        peng = _PENG2NUM[peng]

        candidates = self.__round_state.on_peng(mine, actor, relseat, peng)

        if candidates is None:
            if mine:
                raise RuntimeError("TODO: (A suitable error message)")
            return

        if not isinstance(candidates, list):
            raise RuntimeError(candidates)
        if len(candidates) == 0:
            raise RuntimeError("TODO: (A suitable error message)")
        if not mine:
            raise RuntimeError("TODO: (A suitable error message)")
        return self.__respond(None, candidates)

    def __on_daminggang(self, message: dict) -> None:
        assert message["type"] == "daiminkan"

        if "actor" not in message:
            raise RuntimeError("A `daiminkan` message without the `actor` key.")
        actor = message["actor"]
        if actor < 0 or 4 <= actor:
            raise RuntimeError(
                f"A `daiminkan` message with an invalid `actor` (actor = {actor})."
            )
        mine = actor == self.__game_state.get_seat()

        if "target" not in message:
            raise RuntimeError("A `daiminkan` message without the `target` key.")
        target = message["target"]
        if target < 0 or 4 <= target:
            raise RuntimeError(
                f"A `daiminkan` message with an invalid `target` (target = {target})."
            )
        if actor == target:
            raise RuntimeError(
                f"An inconsistent `daiminkan` message (actor = {actor}, target = {target})."
            )
        relseat = (target + 4 - actor) % 4 - 1

        if "pai" not in message:
            raise RuntimeError("A `daiminkan` message without the `pai` key.")
        tile = message["pai"]
        if tile not in _TILE2NUM:
            raise RuntimeError(
                f"A `daiminkan` message with an invalid `pai` (pai = {tile})."
            )

        if "consumed" not in message:
            raise RuntimeError("A `daiminkan` message without the `consumed` key.")
        consumed = message["consumed"]
        for t in consumed:
            if t not in _TILE2NUM:
                raise RuntimeError(
                    f"A `daiminkan` message with an invalid `consumed` (consumed = {consumed})."
                )

        daminggang = (tile, tuple(consumed))
        if daminggang not in _DAMINGGANG2NUM:
            raise RuntimeError(daminggang)
        daminggang = _DAMINGGANG2NUM[daminggang]

        self.__round_state.on_daminggang(mine, actor, relseat, daminggang)

    def __on_angang(self, message: dict) -> dict:
        assert message["type"] == "ankan"

        seat = self.__game_state.get_seat()

        if "actor" not in message:
            raise RuntimeError("A `ankan` message without the `actor` key.")
        actor = message["actor"]
        if actor < 0 or 4 <= actor:
            raise RuntimeError(
                f"A `ankan` message with an invalid `actor` (actor = {actor})."
            )
        mine = actor == seat

        if "consumed" not in message:
            raise RuntimeError("A `ankan` message without the `consumed` key.")
        consumed = message["consumed"]
        angang = tuple(consumed)

        if angang not in _ANGANG2NUM:
            raise RuntimeError(angang)
        angang = _ANGANG2NUM[angang]

        candidates = self.__round_state.on_angang(seat, actor, angang)
        if mine:
            if candidates is not None:
                raise RuntimeError(candidates)
            return

        if candidates is None:
            return

        if not isinstance(candidates, list):
            raise RuntimeError(candidates)
        if len(candidates) != 2:
            raise RuntimeError(len(candidates))
        # 国士無双の槍槓の可能性があるため，暗槓は打牌とみなす．
        dapai = _TILE2NUM[consumed[0]]
        return self.__respond(dapai, candidates)

    def __on_jiagang(self, message: dict) -> dict:
        assert message["type"] == "kakan"

        seat = self.__game_state.get_seat()

        if "actor" not in message:
            raise RuntimeError("A `kakan` message without the `actor` key.")
        actor = message["actor"]
        if actor < 0 or 4 <= actor:
            raise RuntimeError(
                f"A `kakan` message with an invalid `actor` (actor = {actor})."
            )
        mine = actor == seat

        if "pai" not in message:
            raise RuntimeError("A `kakan` message without the `pai` key.")
        tile = message["pai"]
        if tile not in _TILE2NUM:
            raise RuntimeError(
                f"A `kakan` message with an invalid `pai` (pai = {tile})."
            )
        tile = _TILE2NUM[tile]

        if "consumed" not in message:
            raise RuntimeError("A `kakan` message without the `consumed` key.")
        consumed = message["consumed"]

        candidates = self.__round_state.on_jiagang(seat, actor, tile)
        if mine:
            if candidates is not None:
                raise RuntimeError(candidates)
            return

        if candidates is None:
            return

        if not isinstance(candidates, list):
            raise RuntimeError(candidates)
        if len(candidates) != 2:
            raise RuntimeError(len(candidates))
        return self.__respond(tile, candidates)

    def __on_liqi(self, message: dict) -> None:
        assert message["type"] == "reach"

        if "actor" not in message:
            raise RuntimeError("A `reach` message without the `actor` key.")
        actor = message["actor"]
        if actor < 0 or 4 <= actor:
            raise RuntimeError(
                f"A `reach` message with an invalid `actor` (actor = {actor})."
            )

        self.__round_state.on_liqi(actor)

    def __on_liqi_acceptance(self, message: dict) -> None:
        assert message["type"] == "reach_accepted"

        if "actor" not in message:
            raise RuntimeError("A `reach_accepted` message without the `actor` key.")
        actor = message["actor"]
        if actor < 0 or 4 <= actor:
            raise RuntimeError(
                f"A `reach_accepted` message with an invalid `actor` (actor = {actor})."
            )
        mine = actor == self.__game_state.get_seat()

        self.__game_state.on_liqi_acceptance(actor)
        self.__round_state.on_liqi_acceptance(mine, actor)

    def __on_new_dora(self, message: dict) -> None:
        assert message["type"] == "dora"

        if "dora_marker" not in message:
            raise RuntimeError("A `dora` message without the `dora_marker` key.")
        dora_indicator = message["dora_marker"]
        if dora_indicator not in _TILE2NUM:
            raise RuntimeError(
                f"A `dora` message with an invalid `dora_marker` (dora_marker = {dora_indicator})."
            )
        dora_indicator = _TILE2NUM[dora_indicator]

        self.__round_state.on_new_dora(dora_indicator)

    def __on_hulu(self, message: dict) -> None:
        assert message["type"] == "hora"

        if "actor" not in message:
            raise RuntimeError("A `hora` message without the `actor` key.")
        actor = message["actor"]
        if actor < 0 or 4 <= actor:
            raise RuntimeError(
                f"A `hora` message with an invalid `actor` (actor = {actor})."
            )

        if "target" not in message:
            raise RuntimeError("A `hora` message without the `target` key.")
        target = message["target"]
        if target < 0 or 4 <= target:
            raise RuntimeError(
                f"A `hora` message with an invalid `target` (target = {target})."
            )

        if "pai" not in message:
            raise RuntimeError("A `hora` message without the `pai` key.")
        tile = message["pai"]
        if tile not in _TILE2NUM:
            raise RuntimeError(
                f"A `hora` message with an invalid `pai` (pai = {tile})."
            )

    def __on_luju(self, message: dict) -> None:
        assert message["type"] == "ryukyoku"

        # if 'can_act' not in message:
        #     raise RuntimeError(
        #         'A `ryukyoku` message without the `can_act` key.')
        # can_act = message['can_act']
        # if can_act:
        #     raise RuntimeError(
        #         f'An inconsistent `ryukyoku` message (can_act = {can_act}).')

    def __on_round_end(self, message: dict) -> dict:
        assert message["type"] == "end_kyoku"
        return {"type": "none"}

    def __on_game_end(self, message: dict) -> dict:
        assert message["type"] == "end_game"
        return {"type": "none"}

    def run(self, messages: List[dict]) -> dict:
        ret = None
        while True:
            if len(messages) == 0:
                break
            message = messages[0]
            if "type" not in message:
                raise RuntimeError("A message without the `type` key.")

            if message["type"] == "hello":
                if len(messages) > 1:
                    raise RuntimeError("A multi-line `hello` message.")
                assert ret is None
                ret = self.__on_hello(message)
                messages.pop(0)
                continue

            if message["type"] == "start_game":
                if len(messages) != 1:
                    raise RuntimeError("Too many messages starting with `start_game`.")
                assert ret is None
                ret = self.__on_start_game(message)
                messages.pop(0)
                continue

            if message["type"] == "start_kyoku":
                # if len(messages) < 2:
                #     raise RuntimeError(
                #         'Too few messages starting with `start_kyoku`.')
                self.__on_start_kyoku(message)
                messages.pop(0)
                continue

            if message["type"] == "tsumo":
                assert ret is None
                ret = self.__on_zimo(message)
                messages.pop(0)
                continue

            if message["type"] == "dahai":
                assert ret is None
                ret = self.__on_dapai(message)
                messages.pop(0)
                continue

            if message["type"] == "chi":
                assert ret is None
                ret = self.__on_chi(message)
                messages.pop(0)
                continue

            if message["type"] == "pon":
                assert ret is None
                ret = self.__on_peng(message)
                messages.pop(0)
                continue

            if message["type"] == "daiminkan":
                self.__on_daminggang(message)
                messages.pop(0)
                continue

            if message["type"] == "ankan":
                assert ret is None
                ret = self.__on_angang(message)
                messages.pop(0)
                continue

            if message["type"] == "kakan":
                assert ret is None
                ret = self.__on_jiagang(message)
                messages.pop(0)
                continue

            if message["type"] == "reach":
                self.__on_liqi(message)
                messages.pop(0)
                continue

            if message["type"] == "reach_accepted":
                self.__on_liqi_acceptance(message)
                messages.pop(0)
                continue

            if message["type"] == "dora":
                self.__on_new_dora(message)
                messages.pop(0)
                continue

            if message["type"] == "hora":
                self.__on_hulu(message)
                messages.pop(0)
                continue

            if message["type"] == "ryukyoku":
                self.__on_luju(message)
                messages.pop(0)
                continue

            if message["type"] == "end_kyoku":
                assert ret is None
                ret = self.__on_round_end(message)
                messages.pop(0)
                continue

            if message["type"] == "end_game":
                assert ret is None
                ret = self.__on_game_end(message)
                messages.pop(0)
                if len(messages) > 0:
                    raise RuntimeError("TODO: (A suitable error message)")
                continue

            raise RuntimeError(message)

        if ret is None:
            return {"type": "none"}

        return ret
