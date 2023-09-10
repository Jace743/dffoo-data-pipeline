import yaml
import sqlalchemy as sa
import time
import pandas as pd
import requests
import sys


def main():

    """

    Extract ranks (e.g., S1, S2, EX, LD) from most recent command_abilities json blob.

    """

    config_yml_path = sys.argv[1]

    with open(config_yml_path, 'r') as yml:
        config = yaml.safe_load(yml)


    current_time = str(time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()))

    link_dict = {
        'GL': config['gl_command_abilities'],
        'JP': config['jp_command_abilities']
    }

    df_list = []

    for game_version, link in link_dict.items():

        response = requests.get(link)

        if response.status_code == 200:

            json_content = response.json()

            for ability_id in json_content:
                new_dict = {}

                new_dict['ability_id'] = int(ability_id)
                new_dict['rank'] = str(json_content[ability_id].get('rank', None))
                new_dict['name'] = str(json_content[ability_id].get('name', None))
                new_dict['game_version'] = game_version

                new_df = pd.DataFrame([new_dict])

                df_list.append(new_df)

    ability_rank_df = pd.concat(df_list)

    ability_rank_df['extracted_at_utc'] = current_time

    engine_url = sa.URL.create(
            "postgresql",
            username=config['pg_user'],
            password=config['pg_pass'],
            host=config['pg_host'],
            database=config['pg_db']
        )

    engine = sa.create_engine(engine_url)

    with engine.begin() as conn:
        ability_rank_df.to_sql('raw_ability_ranks', con=conn, index=False, if_exists='replace')

if __name__ == '__main__':
    main()