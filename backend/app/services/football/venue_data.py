"""
五大联赛球场静态数据
包含: 名称、城市、容量、海拔、经纬度、草地类型、是否有顶棚

数据来源: 公开资料汇编
"""

import logging
from ...utils.db import execute_query, execute_many

logger = logging.getLogger('mirofish.football.venue')

# 五大联赛主要球场数据 (精选每联赛 top 球队)
VENUE_DATA = [
    # === Premier League ===
    {'name': 'Old Trafford', 'city': 'Manchester', 'country': 'England', 'capacity': 74310, 'latitude': 53.4631, 'longitude': -2.2913, 'altitude': 40, 'surface': 'grass', 'roof': False, 'built_year': 1910},
    {'name': 'Anfield', 'city': 'Liverpool', 'country': 'England', 'capacity': 61276, 'latitude': 53.4308, 'longitude': -2.9609, 'altitude': 20, 'surface': 'grass', 'roof': False, 'built_year': 1884},
    {'name': 'Etihad Stadium', 'city': 'Manchester', 'country': 'England', 'capacity': 53400, 'latitude': 53.4831, 'longitude': -2.2004, 'altitude': 50, 'surface': 'grass', 'roof': False, 'built_year': 2002},
    {'name': 'Emirates Stadium', 'city': 'London', 'country': 'England', 'capacity': 60704, 'latitude': 51.5549, 'longitude': -0.1084, 'altitude': 40, 'surface': 'grass', 'roof': False, 'built_year': 2006},
    {'name': 'Stamford Bridge', 'city': 'London', 'country': 'England', 'capacity': 40341, 'latitude': 51.4817, 'longitude': -0.1910, 'altitude': 10, 'surface': 'grass', 'roof': False, 'built_year': 1877},
    {'name': 'Tottenham Hotspur Stadium', 'city': 'London', 'country': 'England', 'capacity': 62850, 'latitude': 51.6043, 'longitude': -0.0664, 'altitude': 30, 'surface': 'grass', 'roof': True, 'built_year': 2019},
    {'name': 'St. James\' Park', 'city': 'Newcastle', 'country': 'England', 'capacity': 52305, 'latitude': 54.9755, 'longitude': -1.6217, 'altitude': 60, 'surface': 'grass', 'roof': False, 'built_year': 1892},
    {'name': 'London Stadium', 'city': 'London', 'country': 'England', 'capacity': 62500, 'latitude': 51.5386, 'longitude': -0.0166, 'altitude': 10, 'surface': 'grass', 'roof': True, 'built_year': 2012},
    {'name': 'Villa Park', 'city': 'Birmingham', 'country': 'England', 'capacity': 42657, 'latitude': 52.5092, 'longitude': -1.8847, 'altitude': 140, 'surface': 'grass', 'roof': False, 'built_year': 1897},
    {'name': 'Goodison Park', 'city': 'Liverpool', 'country': 'England', 'capacity': 39414, 'latitude': 53.4388, 'longitude': -2.9664, 'altitude': 20, 'surface': 'grass', 'roof': False, 'built_year': 1892},

    # === La Liga ===
    {'name': 'Santiago Bernabéu', 'city': 'Madrid', 'country': 'Spain', 'capacity': 81044, 'latitude': 40.4531, 'longitude': -3.6883, 'altitude': 650, 'surface': 'grass', 'roof': True, 'built_year': 1947},
    {'name': 'Spotify Camp Nou', 'city': 'Barcelona', 'country': 'Spain', 'capacity': 99354, 'latitude': 41.3809, 'longitude': 2.1228, 'altitude': 50, 'surface': 'grass', 'roof': False, 'built_year': 1957},
    {'name': 'Metropolitano', 'city': 'Madrid', 'country': 'Spain', 'capacity': 68456, 'latitude': 40.4362, 'longitude': -3.5994, 'altitude': 600, 'surface': 'grass', 'roof': True, 'built_year': 2017},
    {'name': 'Ramón Sánchez Pizjuán', 'city': 'Seville', 'country': 'Spain', 'capacity': 43883, 'latitude': 37.3840, 'longitude': -5.9706, 'altitude': 10, 'surface': 'grass', 'roof': False, 'built_year': 1958},
    {'name': 'Benito Villamarín', 'city': 'Seville', 'country': 'Spain', 'capacity': 60721, 'latitude': 37.3564, 'longitude': -5.9818, 'altitude': 10, 'surface': 'grass', 'roof': False, 'built_year': 1929},
    {'name': 'San Mamés', 'city': 'Bilbao', 'country': 'Spain', 'capacity': 53289, 'latitude': 43.2641, 'longitude': -2.9497, 'altitude': 20, 'surface': 'grass', 'roof': True, 'built_year': 2013},
    {'name': 'Mestalla', 'city': 'Valencia', 'country': 'Spain', 'capacity': 49430, 'latitude': 39.4747, 'longitude': -0.3583, 'altitude': 15, 'surface': 'grass', 'roof': False, 'built_year': 1923},
    {'name': 'Anoeta', 'city': 'San Sebastián', 'country': 'Spain', 'capacity': 39500, 'latitude': 43.3013, 'longitude': -1.9736, 'altitude': 20, 'surface': 'grass', 'roof': True, 'built_year': 1993},

    # === Serie A ===
    {'name': 'San Siro', 'city': 'Milan', 'country': 'Italy', 'capacity': 75923, 'latitude': 45.4781, 'longitude': 9.1240, 'altitude': 120, 'surface': 'grass', 'roof': False, 'built_year': 1926},
    {'name': 'Allianz Stadium', 'city': 'Turin', 'country': 'Italy', 'capacity': 41507, 'latitude': 45.1096, 'longitude': 7.6413, 'altitude': 240, 'surface': 'grass', 'roof': False, 'built_year': 2011},
    {'name': 'Stadio Olimpico', 'city': 'Rome', 'country': 'Italy', 'capacity': 70634, 'latitude': 41.9340, 'longitude': 12.4547, 'altitude': 20, 'surface': 'grass', 'roof': False, 'built_year': 1953},
    {'name': 'Stadio Diego Armando Maradona', 'city': 'Naples', 'country': 'Italy', 'capacity': 54726, 'latitude': 40.8279, 'longitude': 14.1931, 'altitude': 10, 'surface': 'grass', 'roof': False, 'built_year': 1959},
    {'name': 'Gewiss Stadium', 'city': 'Bergamo', 'country': 'Italy', 'capacity': 24950, 'latitude': 45.7089, 'longitude': 9.6808, 'altitude': 250, 'surface': 'grass', 'roof': False, 'built_year': 1928},
    {'name': 'Artemio Franchi', 'city': 'Florence', 'country': 'Italy', 'capacity': 43147, 'latitude': 43.7808, 'longitude': 11.2822, 'altitude': 50, 'surface': 'grass', 'roof': False, 'built_year': 1931},

    # === Bundesliga ===
    {'name': 'Allianz Arena', 'city': 'Munich', 'country': 'Germany', 'capacity': 75024, 'latitude': 48.2188, 'longitude': 11.6247, 'altitude': 520, 'surface': 'grass', 'roof': True, 'built_year': 2005},
    {'name': 'Signal Iduna Park', 'city': 'Dortmund', 'country': 'Germany', 'capacity': 81365, 'latitude': 51.4927, 'longitude': 7.4518, 'altitude': 90, 'surface': 'grass', 'roof': True, 'built_year': 1974},
    {'name': 'Olympiastadion', 'city': 'Berlin', 'country': 'Germany', 'capacity': 74475, 'latitude': 52.5148, 'longitude': 13.2394, 'altitude': 40, 'surface': 'grass', 'roof': False, 'built_year': 1936},
    {'name': 'Veltins-Arena', 'city': 'Gelsenkirchen', 'country': 'Germany', 'capacity': 62271, 'latitude': 51.5544, 'longitude': 7.0678, 'altitude': 60, 'surface': 'grass', 'roof': True, 'built_year': 2001},
    {'name': 'Mercedes-Benz Arena', 'city': 'Stuttgart', 'country': 'Germany', 'capacity': 60449, 'latitude': 48.7924, 'longitude': 9.2320, 'altitude': 250, 'surface': 'grass', 'roof': False, 'built_year': 1933},
    {'name': 'Red Bull Arena', 'city': 'Leipzig', 'country': 'Germany', 'capacity': 47069, 'latitude': 51.3459, 'longitude': 12.3482, 'altitude': 115, 'surface': 'grass', 'roof': False, 'built_year': 2004},
    {'name': 'Deutsche Bank Park', 'city': 'Frankfurt', 'country': 'Germany', 'capacity': 51500, 'latitude': 50.0685, 'longitude': 8.6455, 'altitude': 100, 'surface': 'grass', 'roof': True, 'built_year': 2005},
    {'name': 'Volksparkstadion', 'city': 'Hamburg', 'country': 'Germany', 'capacity': 57000, 'latitude': 53.5872, 'longitude': 9.8985, 'altitude': 10, 'surface': 'grass', 'roof': True, 'built_year': 2000},

    # === Ligue 1 ===
    {'name': 'Parc des Princes', 'city': 'Paris', 'country': 'France', 'capacity': 47929, 'latitude': 48.8414, 'longitude': 2.2530, 'altitude': 35, 'surface': 'grass', 'roof': False, 'built_year': 1972},
    {'name': 'Groupama Stadium', 'city': 'Lyon', 'country': 'France', 'capacity': 59186, 'latitude': 45.7653, 'longitude': 4.9822, 'altitude': 200, 'surface': 'grass', 'roof': False, 'built_year': 2016},
    {'name': 'Vélodrome', 'city': 'Marseille', 'country': 'France', 'capacity': 67394, 'latitude': 43.2697, 'longitude': 5.3958, 'altitude': 10, 'surface': 'grass', 'roof': True, 'built_year': 1937},
    {'name': 'Allianz Riviera', 'city': 'Nice', 'country': 'France', 'capacity': 36178, 'latitude': 43.7050, 'longitude': 7.1926, 'altitude': 10, 'surface': 'grass', 'roof': True, 'built_year': 2013},
    {'name': 'Pierre-Mauroy', 'city': 'Lille', 'country': 'France', 'capacity': 50186, 'latitude': 50.6120, 'longitude': 3.1304, 'altitude': 25, 'surface': 'grass', 'roof': True, 'built_year': 2012},
    {'name': 'Roazhon Park', 'city': 'Rennes', 'country': 'France', 'capacity': 29778, 'latitude': 48.1075, 'longitude': -1.7127, 'altitude': 40, 'surface': 'grass', 'roof': False, 'built_year': 1912},
]


def seed_venues():
    """将球场静态数据写入数据库"""
    logger.info(f"开始导入球场数据: {len(VENUE_DATA)} 座球场")

    params_list = [
        (
            v['name'], v['city'], v['country'], v['capacity'],
            v['latitude'], v['longitude'], v['altitude'],
            v['surface'], v['roof'], v['built_year'],
        )
        for v in VENUE_DATA
    ]

    count = execute_many(
        """
        INSERT INTO venues (name, city, country, capacity, latitude, longitude, altitude, surface, roof, built_year)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (name) DO UPDATE SET
            capacity = EXCLUDED.capacity,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            altitude = EXCLUDED.altitude,
            surface = EXCLUDED.surface,
            roof = EXCLUDED.roof,
            updated_at = NOW()
        """,
        params_list,
    )

    logger.info(f"球场数据导入完成: {count} 条记录")
    return count
