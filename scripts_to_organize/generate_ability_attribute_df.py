from web_scraper.web_scraper import CompendiumScraper
import pandas as pd


cs = CompendiumScraper()

cs.character_ability_attribute_omnibus = {}

for char_name in cs.character_dict_omnibus.keys():
    cs.character_ability_attribute_omnibus[char_name] = cs.extract_inline_ability_attributes(char_name)
    
df_rows = []

for char_name, ability_dict in cs.character_ability_attribute_omnibus.items():
    for ability, attribute_list in ability_dict.items():
        df_rows.append({'char_name': char_name, 'ability': ability, 'attributes': attribute_list})

# Create a DataFrame from the list of dictionaries
df = pd.DataFrame(df_rows)

df[df['ability'].apply(lambda x: '(C)' not in x)
    ].reset_index(drop=True).to_csv(
        {path}, 
        index=False)

df[df['ability'].apply(lambda x: '(C)' not in x)
    ].reset_index(drop=True)