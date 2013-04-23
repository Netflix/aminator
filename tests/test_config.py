# -*- coding: utf-8 -*-

#
#
#  Copyright 2013 Netflix, Inc.
#
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.
#
#
from aminator.config import Config


class TestConfig(object):

    def test_simple_dict_merge(self):
        movies = {'comedy': 'The Holy Grail'}
        shows = {'mystery': 'Elementary'}
        movies_shows = dict(movies.items() + shows.items())

        assert movies_shows == Config.dict_merge(movies, shows)

    def test_deeper_dict_merge(self):

        small_dogs = {'dog': {'small': 'poodle'}}
        small_cats = {'cat': {'small': 'tabby'}}

        dogs_and_cats_living_together = {'dog': {'small': 'poodle'}, 'cat': {'small': 'tabby'}}

        assert dogs_and_cats_living_together == Config.dict_merge(small_dogs, small_cats)

    def test_deep_deep_dict_merge(self):

        animaniacs_ages = {'warner bros': {'animaniacs': {'cast': {'Yakko': 1, 'Wacko': 2, 'Dot': 3}}}}
        duck_tales_ages = {'disney': {'duck tales': {'cast': {'Huey': 4, 'Dewey': 5, 'Louie': 6}}}}
        all_ages = {'warner bros': {'animaniacs': {'cast': {'Yakko': 1, 'Wacko': 2, 'Dot': 3}}},
                    'disney': {'duck tales': {'cast': {'Huey': 4, 'Dewey': 5, 'Louie': 6}}}}

        assert all_ages == Config.dict_merge(animaniacs_ages, duck_tales_ages)

