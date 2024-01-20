from collections import defaultdict
import sys
import os

# Add the directory containing your module to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from cogs.score_to_image_cog import GameScores

"""
更新之後，此測試腳本已無用
"""

class TestGameScores(unittest.TestCase):
    def setUp(self):
        """
        T1: 第8名95殺，第6名70殺，第2名5殺，第1名5殺
        T2: 第24名93殺，第21名60殺，第30名22殺，第2名3殺
        T3: 第23名68殺，第11名56殺，第13名18殺，第3名7殺
        T4: 第20名76殺，第10名84殺，第1名11殺，第4名2殺

        排名分
        T1: 第8, 6, 2, 1名 = 4+4+9+12 = 29分
        T2: 第24, 21, 30, 2名 = 0+0+0+9 = 9分
        T3: 第23, 11, 13, 3名 = 0+2+2+8 = 12分
        T4: 第20, 10, 1, 4名 = 0+4+12+7 = 23分

        總擊殺數
        T1: 95+70+5+5 = 175殺
        T2: 93+60+22+3 = 178殺
        T3: 68+56+18+7 = 149殺
        T4: 76+84+11+2 = 173殺

        總擊殺Bonus
        T1: 5分
        T2: 7分
        T3: 0分
        T4: 3分

        總積分（排名分+總擊殺數+總擊殺Bonus）
        T1: 29+175+5 = 209
        T2: 9+178+7 = 194
        T3: 12+149+0 = 161
        T4: 23+173+3 = 199
        """

        self.team_dict = {
            "Team 1": "T1", 
            "Team 2": "T2", 
            "Team 3": "T3", 
            "Team 4": "T4"
        }
        data_dict = {
            "一": [(1, 8, 95), (2, 24, 93), (3, 23, 68), (4, 20, 76)],
            "二": [(1, 6, 70), (2, 21, 60), (3, 11, 56), (4, 10, 84)],
            "三": [(1, 2, 5), (2, 30, 22), (3, 13, 18), (4, 1, 11)],
            "終": [(1, 1, 5), (2, 2, 3), (3, 3, 7), (4, 4, 2)],
        }
        self.game_scores = GameScores(self.team_dict, data_dict, {})

    def test_split_text_to_round_Dict(self):
        raw_text_with_practise_bonus = """
            一
            1, 8, 95
            2, 24, 93
            3, 23, 68
            4, 20, 76

            二
            1, 6, 70
            2, 21, 60
            3, 11, 56
            4, 10, 84

            三
            1, 2, 5
            2, 30, 22
            3, 13, 18
            4, 1, 11

            終
            1, 1, 5
            2, 2, 3
            3, 3, 7
            4, 4, 2

            練習
            1
            3
            4
        """

        expected_keys = ["一", "二", "三", "終", "練習"]

        round_Dict = GameScores._split_text_to_round_Dict(raw_text_with_practise_bonus)
        self.assertListEqual(list(round_Dict.keys()), expected_keys)

    def test_from_raw_text(self):
        raw_text = """
            一
            1, 8, 95
            2, 24, 93
            3, 23, 68
            4, 20, 76

            二
            1, 6, 70
            2, 21, 60
            3, 11, 56
            4, 10, 84

            三
            1, 2, 5
            2, 30, 22
            3, 13, 18
            4, 1, 11

            終
            1, 1, 5
            2, 2, 3
            3, 3, 7
            4, 4, 2
        """
        test_game_scores = GameScores.from_raw_text(self.team_dict, raw_text)
        self.assertDictEqual(test_game_scores.data_dict, self.game_scores.data_dict)

        
    def test_with_practise_bonus(self):
        raw_text_with_practise_bonus = """
            一
            1, 8, 95
            2, 24, 93
            3, 23, 68
            4, 20, 76

            二
            1, 6, 70
            2, 21, 60
            3, 11, 56
            4, 10, 84

            三
            1, 2, 5
            2, 30, 22
            3, 13, 18
            4, 1, 11

            終
            1, 1, 5
            2, 2, 3
            3, 3, 7
            4, 4, 2

            練習
            1: 1
            3: 1
            4: 2
        """

        game_scores = GameScores.from_raw_text(self.team_dict, raw_text_with_practise_bonus)

        expected_output_with_practise_bonus = [
            ('T1', 'Team 1', 175, 29, 6, 210), 
            ('T2', 'Team 2', 178, 9, 7, 194), 
            ('T3', 'Team 3', 149, 12, 1, 162), 
            ('T4', 'Team 4', 173, 23, 5, 201)
        ]
        self.assertListEqual(game_scores.get_sum_of_data(), expected_output_with_practise_bonus)

    def test_get_data_by_type(self):
        result = self.game_scores.get_data_by_type()
        expected = {
            "一": {
                "rankings": [8, 24, 23, 20],
                "ranking_points": [4, 0, 0, 0],
                "kills": [95, 93, 68, 76],
            },
            "二": {
                "rankings": [6, 21, 11, 10],
                "ranking_points": [4, 0, 2, 4],
                "kills": [70, 60, 56, 84],
            },
            "三": {
                "rankings": [2, 30, 13, 1],
                "ranking_points": [9, 0, 2, 12],
                "kills": [5, 22, 18, 11],
            },
            "終": {
                "rankings": [1, 2, 3, 4],
                "ranking_points": [12, 9, 8, 7],
                "kills": [5, 3, 7, 2],
            },
        }

        self.assertDictEqual(result, expected)

    def test_get_sum_of_data(self):
        result = self.game_scores.get_sum_of_data()
        expected = [
            ("T1", "Team 1", 175, 29, 5, 209),
            ("T2", "Team 2", 178, 9, 7, 194),
            ("T3", "Team 3", 149, 12, 0, 161),
            ("T4", "Team 4", 173, 23, 3, 199),
        ]
        self.assertEqual(result, expected)

    def test_get_data_for_image_format(self):
        result = self.game_scores.get_data_for_image_format()
        expected = [
            ('T1', 'T4', 'T2', 'T3'),
            ('Team 1', 'Team 4', 'Team 2', 'Team 3'),
            (175, 173, 178, 149),
            (209, 199, 194, 161),
        ]
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
