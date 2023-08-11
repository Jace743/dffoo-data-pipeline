import pandas as pd
import sys
import time
import re
import contextlib
import yaml
import io
import requests
import logging
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains


class CompendiumScraper:
    """

    A class to scrape the Dissidia Compendium website.

    """
    
    def __init__(self, config_yml_path):
        self.chars_with_reworks_pending = []
        self.chars_not_in_gl_yet = []
        self.character_list_url = 'https://dissidiacompendium.com/characters/?'
        
        with open(config_yml_path, 'r') as yml:
            self.config = yaml.safe_load(yml)

        # Start up logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s')
        file_handler = logging.FileHandler(self.config['logging_dir'])
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(message)s')
        file_handler.setFormatter(formatter)
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(file_handler)
        self.logger.removeHandler(logging.StreamHandler)  # Prevent logging in the console.
        self.LOG_DIVIDER = "===================================================="
        
        # Dictionary used for processing abilities that have one HP attack uncapped, with all the others 
        # regularly capped.
        self.N_HP_ATTACKS_UNCAPPED = {
            'Chuck Staff': {
                'followup_name': 'Chuck Staff (Uncapped HP Attack)', 
                'gl_hp_attack_count_main': 1,
                'jp_hp_attack_count_main': 1,
                'gl_hp_attack_count_non': 1,
                'jp_hp_attack_count_non': 1
            },

            'Crystal Ray': {
                'followup_name': 'Crystal Ray (Uncapped HP Attack)',  
                'gl_hp_attack_count_main': 1,
                'jp_hp_attack_count_main': 1,
                'gl_hp_attack_count_non': 1,
                'jp_hp_attack_count_non': 1
            },
            'Soul Burst': {
                'followup_name': 'Soul Burst (Uncapped HP Attack)',  
                'gl_hp_attack_count_main': 1,
                'jp_hp_attack_count_main': 1,
                'gl_hp_attack_count_non': 0,
                'jp_hp_attack_count_non': 0
            },
            'Soul Burst+': {
                'followup_name': 'Soul Burst+ (Uncapped HP Attack)', 
                'gl_hp_attack_count_main': 1,
                'jp_hp_attack_count_main': 2,
                'gl_hp_attack_count_non': 0,
                'jp_hp_attack_count_non': 0
            },
        }

        self.driver = webdriver.Chrome()

        self.generate_character_links()

        self.logger.info("Character links successfully generated.")

        self.ability_dict_omnibus_gl = {}
        self.bt_effect_dict_omnibus_gl = {}
        self.ha_dict_omnibus_gl = {}
        
        self.ability_dict_omnibus_jp = {}
        self.bt_effect_dict_omnibus_jp = {}
        self.ha_dict_omnibus_jp = {}
    
    def generate_character_links(self):
        """

        Generates a dictionary with character names as the keys. Values for these keys are
        dictionaries, which contain links to the character's profile, ability, buff,
        high armor, and high armor plus pages.

        """

        self.driver.get(self.character_list_url)
        
        character_link_list = WebDriverWait(
            self.driver,
            timeout=10
        ).until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "characterlink"))
        )

        self.logger.info(self.LOG_DIVIDER)
        self.logger.info("Retrieved all main character links. Generating remaining links for each character.")
        self.logger.info(self.LOG_DIVIDER)
    
        self.character_dict_omnibus = {}
        
        for char_link in character_link_list:
            char_name = str(char_link.get_attribute("href").split('/')[-1])
            link_to_profile = str(char_link.get_attribute("href"))
            link_to_abilities = str(f"https://dissidiacompendium.com/characters/{char_name}/abilities?")
            link_to_buffs = str(f"https://dissidiacompendium.com/characters/{char_name}/buffs?")
            link_to_ha = str(f"https://dissidiacompendium.com/characters/{char_name}/gear?7A=true")
            link_to_ha_plus = str(f"https://dissidiacompendium.com/characters/{char_name}/gear?7APlus=true")
            
            char_dict = {
                    'profile_url': link_to_profile,
                    'abilities_url': link_to_abilities,
                    'buffs_url': link_to_buffs,
                    'high_armor_url': link_to_ha,
                    'high_armor_plus_url': link_to_ha_plus
            }
            
            self.character_dict_omnibus[char_name] = char_dict

            self.logger.info("self.character_dict_omnibus entry for %s was successful", char_name.upper())


    def prettify_html_to_list(self, html_element):
        """
    
        Retrieves the 'outerHTML' attribute of an HTML element, parses it, and  
        returns a list to enable iteration over the HTML element.
    
        """
        
        soup = BeautifulSoup(html_element.get_attribute('outerHTML'), 'lxml')
    
        return [line for line in soup.prettify().split('\n')]


    def generate_ability_dict(
        self,
        char_name,  # Character name, as a string
        scroll_speed = 1000,  # Scrolling speed to move through the page for lazy loading
        verbose = False,  # If true, will return print statements on iterations
        JP = False,
        return_output = False  # If true, will return output in addition to adding to class attribute
    ):
        """
    
        Parses a character's ability page to college abilities with HP attacks in them. The function
        returns an ability dictionary, where the keys are the ability names in human-readable
        format, and the values are the <div> block containing the number of BRV attacks, HP
        attacks, buffs granted, attack attributes, etc. of the ability

        This function also checks whether the character has a JP rework. I couldn't think of a 
        better place to nest that functionality, because I didn't want the scraper to make
        170+ additional requests just to do one thing. 
    
        """
    
        self.logger.info(self.LOG_DIVIDER)
        self.logger.info("Generating ability dictionary for %s", char_name.upper())
        self.logger.info(self.LOG_DIVIDER)

        try:
            self.driver.get(self.character_dict_omnibus[char_name]['abilities_url'])
        except:
            print("You need to generate the character_dict_omnibus first (run generate_character_links).")
            self.logger.info("User didn't generate character_dict_omnibus first.")
            return
    
        time.sleep(5)

        actions = ActionChains(self.driver)
        
        if JP:
            try:
                switch_to_jp_button = self.driver.find_element(By.XPATH, "//span[@class='glflage smalleventbutton']")

                actions.click(switch_to_jp_button).perform()

                time.sleep(5)
            except:
                pass
        elif not JP:
            try:
                switch_to_gl_button = self.driver.find_element(By.XPATH, "//span[@class='jpflage jpsmallinactive smalleventbutton']")

                actions.click(switch_to_gl_button).perform()

                time.sleep(5)
            except:
                pass
        
        if not JP:
            self.screen_for_rework(char_name)

        try:
            # Just want to test that this can run. Don't want an output.
            with contextlib.redirect_stdout(io.StringIO()):
                self.driver.find_element(By.XPATH, "//div[@class='infotitle abilitydisplayfex ']")
        except:
            self.logger.info("Unable to access abilities for %s.", char_name.upper())
            if not JP:
                self.logger.info("They might not be released to GL yet.")
                if char_name not in self.chars_not_in_gl_yet:
                    self.chars_not_in_gl_yet.append(char_name)
                return
            else:
                self.logger.info("Something's wrong with ability_dict generation for %s, since we're already checking the JP version.", char_name.upper())
                return
        
        
        
        list_build_complete = False
        
        count = 0
        
        while list_build_complete == False:
            
            self.driver.execute_script(f"window.scrollBy(0, {scroll_speed});")
            time.sleep(1)
            ability_list = self.driver.find_elements(By.XPATH, "//div[@class='infotitle abilitydisplayfex ']")
            
            # The last two abilities are calls. So,h the second to last ability should be a call when we're done.
            match = re.search('\(C\)', ability_list[-2].text)
            list_build_complete = True if match else False
            
            self.logger.info("This iteration caught %s abilities.", len(ability_list))
        
            self.logger.info('-----------')
            count += 1
            if count == 15:
                self.logger.info("Too many iterations. Examine this function for: %s", char_name.upper())
                break
        
        self.logger.info("This took %s iterations.", count)
    
        for ability in ability_list:
            self.logger.info("%s", ability.text)
    
        ability_second_div_list = self.driver.find_elements(By.XPATH, "//div[@class='bluebase abilityinfobase']")
    
        self.logger.info("Collected ability info list for %s", char_name)
        
        ability_dict = {}
        
        for index, ability_first_div in enumerate(ability_list):
            
            ability_name = str(ability_first_div.text.split(' - ')[0])
            
            ability_dict[ability_name] = {}
            
            ability_dict[ability_name]['ability_attack_info'] = ability_second_div_list[index]

            inline_attribute_list  = []
            
            ability_first_div_html = self.prettify_html_to_list(ability_first_div)
        
            for line in ability_first_div_html:
                if re.search(r"inline ", line):
                    inline_attribute = re.search(r"(inline )(\w+)", line).group(2)
                    inline_attribute_list.append(inline_attribute)
        
            ability_dict[ability_name]['attribute_list'] = inline_attribute_list
    
        self.logger.info('Finished extracting inline attributes for %s', char_name.upper())
        
        if not JP:
            
            self.ability_dict_omnibus_gl[char_name] = {}
            self.ability_dict_omnibus_gl[char_name] = ability_dict

        elif JP:
            
            self.ability_dict_omnibus_jp[char_name] = {}
            self.ability_dict_omnibus_jp[char_name] = ability_dict
        
        if return_output:
            return ability_dict
        

    def parse_ability_dict_to_df(
        self,
        char_name,  # Character name, as a string
        JP = False  # If True, will pull from the JP version of ability_dict_omnibus instead of the GL version
    ):
        """
    
        Extracts the number of HP attacks dealt to an ability's main target and non-targets. The
        function input should be a character name (char_name) in string format. Pulls data from
        self.ability_dict_omnibus, so `generate_ability_dict` should be run for the character
        beforehand.
    
        Returns a pandas dataframe with the ability name, number of HP attacks into main targets, 
        number of HP attacks into non-targets, and ability attribute list.
    
        """

        self.logger.info(self.LOG_DIVIDER)
        self.logger.info("Parsing ability dict to df for %s.", char_name.upper())
        self.logger.info(self.LOG_DIVIDER)

        try:
            if not JP:
                ability_dictionary = self.ability_dict_omnibus_gl[char_name]
            elif JP:
                ability_dictionary = self.ability_dict_omnibus_jp[char_name]
        except:
            print(f"No ability_dict for {char_name}.")
            print(f"Run `generate_ability_dict('{char_name}')` first, then `parse_ability_dict_to_df()` should work for them.")
            print("Also, make sure you've properly specified whether you want the GL or JP version for both functions.")
            self.logger.info("Couldn't find ability_dict for %s.", char_name.upper())
            return

        df_row_list = []
        
        for ability_name in ability_dictionary.keys():
        
            ability_html_lines = self.prettify_html_to_list(
                ability_dictionary[ability_name]['ability_attack_info']
                )
        
            row_dict = {}
    
            row_dict['ability_name'] = ability_name
            
            main_target_hp_attacks = 0
            non_target_hp_attacks = 0
            hp_dmg_cap_up_perc = 0
    
            for index, line in enumerate(ability_html_lines):
                
                # Extract HP Dmg Cap within ability and/or from FE
                
                if re.search("- MAX BRV Cap", line):
                    hp_dmg_cap_up_perc += int(ability_html_lines[index + 6].strip().replace('%', ''))
                
                if re.search("MAX BRV Cap Up by", line):
                    hp_dmg_cap_up_perc += int(ability_html_lines[index + 2].strip().replace('%', ''))
                
                # "inline HP" is class for the HP Attack icon
                if "inline HP" not in line:
                    continue
                
                # Info on single-target vs group attack appears on preceding line and/or 3 lines before
                
                single_or_group_lines = ability_html_lines[index - 1] + ability_html_lines[index - 3] + ability_html_lines[index + 2]
                
                AOE = True if re.search(r"Group", single_or_group_lines) else False
    
                # Sometimes an inline appears after the inline(s) we care about to describe the source 
                # of the HP damage. We want to skip these instances.
                if re.search(r"Attack", ability_html_lines[index - 2]):
                    continue
                
                # Info on HP attack count and type appears two lines later (e.g., Attack 3 times,
                # Damage to non-targets after each HP attack, etc.), with a few exceptions.
    
                # I hate hard coding an ability name like this, but we'll see if I can make it more
                # programmatic later, or make a list of abilities that operate with this format.
                
                if ability_name == 'Crystal Generation':
                    attack_info_line = ability_html_lines[index + 6]
                else:
                    attack_info_line = ability_html_lines[index + 2]
    
                extra_condition_line = ability_html_lines[index + 6]
    
                # Some abilities deal damage based on a stored value (e.g., Aerith BT effect, Astos)
                # For these abilities, the line we want appears eleven lines later
                if re.search(r"Damage by", attack_info_line) and re.search(r"of stored value from", extra_condition_line):
                    attack_info_line = ability_html_lines[index + 11]
                
                # Other abilities deal damage based on a characters stat or current value (e.g., Aerith's LD followup)
                # For these abilities, the line we want appears six lines later
                if re.search(r"Damage ", attack_info_line) and re.search(r"of ", extra_condition_line):
                    attack_info_line = ability_html_lines[index + 6]
            
                hp_attacks_to_add = 0
                add_to_non_target = 0
                copy_st_to_aoe = False
            
                if re.search(r"Damage to non-targets after each HP Attack", attack_info_line):
                    copy_st_to_aoe = True
                elif re.search(r"Group \d+", attack_info_line):
                    AOE = True
                    hp_attacks_to_add = int(re.search(r"Group \d+ times", attack_info_line).group().split(' ')[1])
                elif re.search(r"Group", attack_info_line):
                    AOE = True
                    hp_attacks_to_add = 1
                elif re.search(r"to non-targets × \d+", attack_info_line):
                    add_to_non_target = int(re.search(r"× \d+", attack_info_line).group().split(' ')[1])
                elif re.search(r"to non-targets \d+ times", attack_info_line):
                    add_to_non_target = int(re.search(r"\d+ times", attack_info_line).group().split(' ')[0])
                elif re.search(r"to non-targets", attack_info_line):
                    add_to_non_target = 1
                elif re.search(r"\d+ times", attack_info_line):
                    hp_attacks_to_add = int(re.search("\d+ times", attack_info_line).group().split(' ')[0])
                else:
                    hp_attacks_to_add = 1
            
                if AOE:
                    main_target_hp_attacks += hp_attacks_to_add
                    non_target_hp_attacks += hp_attacks_to_add
                elif copy_st_to_aoe:
                    non_target_hp_attacks = main_target_hp_attacks
                else:
                    main_target_hp_attacks += hp_attacks_to_add
                    non_target_hp_attacks += add_to_non_target
            
            row_dict['main_target_hp_attacks'] = main_target_hp_attacks
            row_dict['non_target_hp_attacks'] = non_target_hp_attacks
            row_dict['hp_dmg_cap_up_perc'] = hp_dmg_cap_up_perc

            
            # Add ability attribute column
            row_dict['attribute_list'] = ability_dictionary[ability_name]['attribute_list']
            row_dict['game_version'] = 'GL' if not JP else 'JP'

            # Handling for abilities with one uncapped HP attack
            if ability_name in self.N_HP_ATTACKS_UNCAPPED.keys() and not JP:
                special_row_dict = {}
                row_dict['main_target_hp_attacks'] = main_target_hp_attacks - self.N_HP_ATTACKS_UNCAPPED[ability_name]['gl_hp_attack_count_main']
                row_dict['non_target_hp_attacks'] = non_target_hp_attacks = self.N_HP_ATTACKS_UNCAPPED[ability_name]['gl_hp_attack_count_non']

                special_row_dict['ability_name'] = self.N_HP_ATTACKS_UNCAPPED[ability_name]['followup_name']
                special_row_dict['main_target_hp_attacks'] = self.N_HP_ATTACKS_UNCAPPED[ability_name]['gl_hp_attack_count_main']
                special_row_dict['non_target_hp_attacks'] = self.N_HP_ATTACKS_UNCAPPED[ability_name]['gl_hp_attack_count_non']
                special_row_dict['hp_dmg_cap_up_perc'] = 900  # Takes a character from 99,999 dmg to 999,999 dmg
                special_row_dict['attribute_list'] = ['FollowUp'] + ability_dictionary[ability_name]['attribute_list'] if 'FollowUp' not in ability_dictionary[ability_name]['attribute_list'] else ability_dictionary[ability_name]['attribute_list']
                special_row_dict['game_version'] = 'GL'

                df_row_list.append(special_row_dict)
            
            elif ability_name in self.N_HP_ATTACKS_UNCAPPED.keys() and JP:
                special_row_dict = {}
                row_dict['main_target_hp_attacks'] = main_target_hp_attacks - self.N_HP_ATTACKS_UNCAPPED[ability_name]['jp_hp_attack_count_main']
                row_dict['non_target_hp_attacks'] = non_target_hp_attacks = self.N_HP_ATTACKS_UNCAPPED[ability_name]['jp_hp_attack_count_non']

                special_row_dict['ability_name'] = self.N_HP_ATTACKS_UNCAPPED[ability_name]['followup_name']
                special_row_dict['main_target_hp_attacks'] = self.N_HP_ATTACKS_UNCAPPED[ability_name]['jp_hp_attack_count_main']
                special_row_dict['non_target_hp_attacks'] = self.N_HP_ATTACKS_UNCAPPED[ability_name]['jp_hp_attack_count_non']
                special_row_dict['hp_dmg_cap_up_perc'] = 900  # Takes a character from 99,999 dmg to 999,999 dmg
                special_row_dict['attribute_list'] = ['FollowUp'] + ability_dictionary[ability_name]['attribute_list'] if 'FollowUp' not in ability_dictionary[ability_name]['attribute_list'] else ability_dictionary[ability_name]['attribute_list']
                special_row_dict['game_version'] = 'JP'

                df_row_list.append(special_row_dict)

            df_row_list.append(row_dict)
    
        ability_df = pd.DataFrame(df_row_list)

        ability_df['char_name'] = char_name

        self.logger.info("Sucessfully converted ability df for %s", char_name.upper())
        
        return ability_df[['char_name', 'ability_name', 'main_target_hp_attacks', 'non_target_hp_attacks', 'hp_dmg_cap_up_perc', 'attribute_list']]

    def retrieve_hp_caps_from_bt(
        self,
        char_name,  # Character's name as a string
        verbose = False,  # If true, will return print statements
        JP = False, # If true, will check the JP version of the website instead of GL
        return_output = False # If true, will return a pandas dataframe row after running
    ):
    
        """
    
        Takes a character's name as input and adds a key-value pair to self.bt_effect_dict_omnibus. Key is char_name, and
        the value is a dictionary with three key-value pairs:
    
        1) Character's name
        2) Personal HP Dmg Cap up from BT effect
        3) Party-side HP Dmg Cap up from BT effect
        
        """
    
        self.logger.info(self.LOG_DIVIDER)
        self.logger.info("Retrieving BT info for %s.", char_name.upper())
        self.logger.info(self.LOG_DIVIDER)

        actions = ActionChains(self.driver)
        
        self.driver.get(self.character_dict_omnibus[char_name]['buffs_url'])
        
        time.sleep(5)

        if JP:
            try:
                switch_to_jp_button = self.driver.find_element(By.XPATH, "//span[@class='glflage smalleventbutton']")

                actions.click(switch_to_jp_button).perform()

                time.sleep(5)
            except:
                pass
        elif not JP:
            try:
                switch_to_gl_button = self.driver.find_element(By.XPATH, "//span[@class='jpflage jpsmallinactive smalleventbutton']")

                actions.click(switch_to_gl_button).perform()

                time.sleep(5)
            except:
                pass
        
        bt_personal_hp_dmg_cap_up = 0
        bt_party_hp_dmg_cap_up = 0
        
        try:
            # Find the BT button for the character's buff page
            bt_button_element = self.driver.find_element(By.XPATH, "//li[@class='filterinactive buffbutton wpbtbutton']")
        except:
            print(f"Unable to find a BT for {char_name.title()}. Either the character isn't in GL yet, or they lack a BT in both GL and JP.")
            self.logger.info("Couldn't find BT button for %s", char_name.upper())
            return
            
        # Click on it to make sure that the buff appears
        actions.click(bt_button_element)
        
        # Scroll down to make sure the BT buff loads fully
        self.driver.execute_script(f"window.scrollBy(0, 600);")
        
        time.sleep(1)

        # Set leveled BT to max before extracting auras
        try:
            if self.driver.find_element(By.XPATH, "//div[@class='sliderbase infonameholder nobuffpadding']"):
                
                pretty_div_block_list = self.prettify_html_to_list(
                    self.driver.find_element(
                        By.XPATH, "//div[@class='sliderbase infonameholder nobuffpadding']"
                    )
                )
        
                # Note to self for later -- not relevant for actual code
                if char_name in ['lannreynn', 'paine']:
                    print(
                        f"NOTE: {char_name.upper()} has something about them"
                    )
                    print(
                        "that you need to consider before adding new features!"
                    )
                    
                try:
                    # find slider class
                    for line in pretty_div_block_list:
                        if re.search(r'css-(\w+)-Slider', line):
                            slider_class = re.search(r'css-\w+-Slider', line).group()
        
                    # Find width element class
                    for line in pretty_div_block_list:
                        if re.search(r'(css-\w+)(" style)', line):
                            width_element_class = re.search(r'(css-\w+)(" style)', line).group(1)
                    
                    slider = self.driver.find_element(By.XPATH, f"//div[@class='{slider_class}']")
                    width_element = self.driver.find_element(By.XPATH, f"//div[@class='{width_element_class}']")
                    
                except:
                    print("There's a new BT Effect slider for you to figure out.")
                    self.logger.info("Unable to account for BT Effect slider for %s.", char_name.upper())
                    return
        
            offset = 80
        
            while width_element.get_attribute('style') != 'width: 100%;':
                offset += 10
                actions.drag_and_drop_by_offset(slider, offset, 0).release().perform()
                self.logger.info("Offset of %s performed.", offset)
        
            self.logger.info("Reached max stacks!")
        except:
            self.logger.info(f"No stack slider found. Assuming {char_name} has a BT without stacks.")
            pass
        
        bt_buff_description_div = self.driver.find_element(
            By.XPATH, "//div[@class='Buffbase infobase nobuffpadding']"
        )
        
        bt_buff_html_list = self.prettify_html_to_list(bt_buff_description_div)
        
        for index, line in enumerate(bt_buff_html_list):
            
            if re.search(r"- MAX BRV Cap", line):  # Personal HP Dmg Cap Up has this string
                bt_personal_hp_dmg_cap_up += int(re.search(r"\d+", bt_buff_html_list[index + 6]).group())
            if re.search(r"- Party MAX BRV Cap", line):  # Party HP Dmg Cap up has this string
                bt_party_hp_dmg_cap_up += int(re.search(r"\d+", bt_buff_html_list[index + 6]).group())
    
        bt_effect_dict = {}
        bt_effect_dict['char_name'] = char_name
        bt_effect_dict['bt_personal_hp_dmg_cap_up'] = bt_personal_hp_dmg_cap_up
        bt_effect_dict['bt_party_hp_dmg_cap_up'] = bt_party_hp_dmg_cap_up
    
        if not JP:
            
            bt_effect_dict['game_version'] = 'GL'
            self.bt_effect_dict_omnibus_gl[char_name] = bt_effect_dict

        elif JP:
            
            bt_effect_dict['game_version'] = 'JP'
            self.bt_effect_dict_omnibus_jp[char_name] = bt_effect_dict
        
        self.logger.info("Retrieved BT info for %s.", char_name.upper())
        
        if return_output:
            bt_effect_df = pd.DataFrame([bt_effect_dict])

            return bt_effect_df

    def retrieve_ha_hp_dmg_cap_up(self, char_name, verbose=False, JP=False, return_output=False):
        """
    
        Retrieves HP Dmg Cap up values from a character's high armor pages, both personal and 
        party-wide, and adds character key-value pair to self.ha_dict_omnibus, where the key is char_name and the
        value is a dict with  three key-value pairs: 1) character name, 2) personal hp dmg cap up, 
        and 3) party-wide hp dmg cap up.
    
        """
        self.logger.info(self.LOG_DIVIDER)
        self.logger.info("Retrieving High Armor info for %s.", char_name.upper())
        self.logger.info(self.LOG_DIVIDER)
        
        self.driver.get(self.character_dict_omnibus[char_name]['high_armor_url'])
        
        time.sleep(5)

        actions = ActionChains(self.driver)
        
        if JP:
            try:
                switch_to_jp_button = self.driver.find_element(By.XPATH, "//span[@class='glflage smalleventbutton']")

                actions.click(switch_to_jp_button).perform()

                time.sleep(5)
            except:
                pass
        elif not JP:
            try:
                switch_to_gl_button = self.driver.find_element(By.XPATH, "//span[@class='jpflage jpsmallinactive smalleventbutton']")

                actions.click(switch_to_gl_button).perform()

                time.sleep(5)
            except:
                pass
        try:
            high_armor_html = self.prettify_html_to_list(
                self.driver.find_element(By.XPATH, "//div[@class='infonameholderenemybuff default_passive Buffbase']")
            )
        except:
            self.logger.info("Could not find High Armor for %s.", char_name.upper())
            print(f"Unable to find High Armor info for {char_name.title()}.")
            if not JP:
                print("They might not be released to GL yet.")
                if char_name not in self.chars_not_in_gl_yet:
                    self.chars_not_in_gl_yet.append(char_name)
                return
            else:
                self.logger.info("Something's wrong with high armor parsing for %s, since we're already checking the JP version.", char_name.upper())
                return
        
        personal_ha_hp_dmg_cap_up = 0
        party_ha_hp_dmg_cap_up = 0
        
        # Extract base high armor values
        for index, line in enumerate(high_armor_html):
            if re.search(r"- MAX BRV Cap", line):
                personal_ha_hp_dmg_cap_up += int(re.search("\d+", high_armor_html[index + 6]).group())
            if re.search(r"- Party MAX BRV Cap", line):
                party_ha_hp_dmg_cap_up += int(re.search("\d+", high_armor_html[index + 6]).group())
        
        self.driver.get(self.character_dict_omnibus[char_name]['high_armor_plus_url'])
        
        time.sleep(5)
        
        self.driver.execute_script("window.scrollBy(0, 300);")
        
        high_armor_plus_div_list = self.driver.find_elements(
            By.XPATH, "//div[@class='infonameholderenemybuff default_passive Buffbase']"
        )
        
        # Make sure we've captured all the HA+ blocks before extracting data
        while len(high_armor_plus_div_list) < 5:
            self.driver.execute_script("window.scrollBy(0, 300);")
            high_armor_plus_div_list = self.driver.find_elements(
                By.XPATH, "//div[@class='infonameholderenemybuff default_passive Buffbase']"
            )
        
        for div_block in high_armor_plus_div_list:
            
            ha_plus_html = self.prettify_html_to_list(div_block)
            
            for index, line in enumerate(ha_plus_html):
                if re.search(r"- MAX BRV Cap", line):
                    personal_ha_hp_dmg_cap_up += int(re.search(
                        "\d+", ha_plus_html[index + 6]
                    ).group())
        
                if re.search(r"- Party MAX BRV Cap", line):
                    party_ha_hp_dmg_cap_up += int(re.search(
                        "\d+", ha_plus_html[index + 6]
                    ).group())
    
        ha_hp_dmg_cap_up_dict = {}
        ha_hp_dmg_cap_up_dict['char_name'] = char_name
        ha_hp_dmg_cap_up_dict['personal_hp_dmg_cap_up'] = personal_ha_hp_dmg_cap_up
        ha_hp_dmg_cap_up_dict['party_ha_hp_dmg_cap_up'] = party_ha_hp_dmg_cap_up
    
        if not JP:
            
            ha_hp_dmg_cap_up_dict['game_version'] = 'GL'
            self.ha_dict_omnibus_gl[char_name] = ha_hp_dmg_cap_up_dict

        elif JP:
            
            ha_hp_dmg_cap_up_dict['game_version'] = 'JP'
            self.ha_dict_omnibus_jp[char_name] = ha_hp_dmg_cap_up_dict
        
        self.logger.info("High armor info parsed for %s.", char_name.upper())
        
        if return_output:
            ha_hp_dmg_cap_up_df = pd.DataFrame([ha_hp_dmg_cap_up_dict])

            return ha_hp_dmg_cap_up_df
    
    def screen_for_rework(self, char_name):
        """
        
        Checks whether a character has had a rework in the Japanese version of the game. If so, this function
        will add them to the characters with reworks list to be parsed later. 
        
        """

        try:
            if self.driver.find_element(By.XPATH, "//li[@class='filterinactive buffbutton reworktabred_direct']"):
                self.chars_with_reworks_pending.append(char_name)
                self.logger.info("Found an upcoming rework for %s.", char_name.upper())
        except:
            return
        
    def extract_character_main_image(self, 
                                     char_name, 
                                     output_dir = None):
        """
        
        Downloads a character's main image from Dissidia Compendium and stores it locally. 
        
        """

        try:
            if output_dir is None:
                output_dir = self.config['images_dir']
        except:
            ValueError("You need to provide an output_dir or use a config yml")
            return

        try:
            self.driver.get(self.character_dict_omnibus[char_name]['profile_url'])
        except:
            print(f"Couldn't find profile link for {char_name.title()}.")

        output_file_path = output_dir + f"{char_name}_main_image.jpg"
        
        time.sleep(5)
        
        image_element = self.driver.find_element(By.XPATH, "//img[@class='charmanimage']")

        link = image_element.get_attribute('src')

        response = requests.get(link)

        if response.status_code == 200:
            with open(output_file_path, 'wb') as f:
                f.write(response.content)
        
        else:
            print(f"Accessed profile url, but could not access image url for {char_name.title()}")
    

def main():
    """
    
    One function that will complete all standard web scraping operations.
    
    """

    config_yml_path = sys.argv[1]

    cs = CompendiumScraper(config_yml_path)

    ability_df_list = []

    bt_effect_df_list = []

    ha_cap_df_list = []
    
    character_count = 1

    for char_name in cs.character_dict_omnibus.keys():
        
        # Restart the driver every once in a while so program doesn't crash
        if character_count in [30, 60, 90, 120, 150, 180]:
            cs.driver.close()
            cs.driver = webdriver.Chrome()
            time.sleep(5)

        cs.generate_ability_dict(char_name)
    
        parsed_ability_df = cs.parse_ability_dict_to_df(char_name)

        ability_df_list.append(parsed_ability_df)
    
        bt_effect_df = cs.retrieve_hp_caps_from_bt(char_name, return_output=True)

        bt_effect_df_list.append(bt_effect_df)
    
        high_armor_cap_df = cs.retrieve_ha_hp_dmg_cap_up(char_name, return_output=True)

        ha_cap_df_list.append(high_armor_cap_df)

        try:
            parsed_ability_df.to_csv(cs.config['temp_ability_df_dir'] + f"{char_name}_abiilty_df_gl.csv", index=False)
            cs.logger.info("Successfully saved temporary ability_df for %s.", char_name.upper())
        except:
            cs.logger.info("No ability_df to save for %s.", char_name.upper())
            pass
        
        try:
            bt_effect_df.to_csv(cs.config['temp_bt_effect_df_dir'] + f"{char_name}_bt_effect_df_gl.csv", index=False)
            cs.logger.info("Successfully saved temporary bt_effect_df for %s.", char_name.upper())
        except:
            cs.logger.info("No bt_effect_df to save for %s.", char_name.upper())
            pass
        
        try:
            high_armor_cap_df.to_csv(cs.config['temp_ha_cap_df_dir'] + f"{char_name}_ha_cap_df_gl.csv", index=False)
            cs.logger.info("Successfully saved temporary ha_cap_df for %s.", char_name.upper())
        except:
            cs.logger.info("No high_armor_cap_df to save for %s.", char_name.upper())
            pass

        character_count += 1

    cs.jp_scrape_set = set(cs.chars_with_reworks_pending + cs.chars_not_in_gl_yet)
    
    character_count = 1

    cs.logger.info(cs.LOG_DIVIDER)
    cs.logger.info("BEGIN PARSING JP VERSION")
    cs.logger.info(cs.LOG_DIVIDER)

    for char_name in cs.jp_scrape_set:
        # Restart the driver every once in a while so program doesn't crash
        if character_count in [30, 60, 90, 120, 150, 180]:
            cs.driver.close()
            cs.driver = webdriver.Chrome()
            time.sleep(5)
        
        cs.generate_ability_dict(char_name, JP=True)
    
        parsed_ability_df = cs.parse_ability_dict_to_df(char_name, JP=True)

        ability_df_list.append(parsed_ability_df)
    
        bt_effect_df = cs.retrieve_hp_caps_from_bt(char_name, JP=True, return_output=True)

        bt_effect_df_list.append(bt_effect_df)
    
        high_armor_cap_df = cs.retrieve_ha_hp_dmg_cap_up(char_name, JP=True, return_output=True)

        ha_cap_df_list.append(high_armor_cap_df)
        
        try:
            parsed_ability_df.to_csv(cs.config['temp_ability_df_dir'] + f"{char_name}_abiilty_df_jp.csv", index=False)
            cs.logger.info("Successfully saved temporary ability_df for %s.", char_name.upper())
        except:
            cs.logger.info("No ability_df to save for %s.", char_name.upper())
            pass
        
        try:
            bt_effect_df.to_csv(cs.config['temp_bt_effect_df_dir'] + f"{char_name}_bt_effect_df_jp.csv", index=False)
            cs.logger.info("Successfully saved temporary bt_effect_df for %s.", char_name.upper())
        except:
            cs.logger.info("No bt_effect_df to save for %s.", char_name.upper())
            pass
        
        try:
            high_armor_cap_df.to_csv(cs.config['temp_ha_cap_df_dir'] + f"{char_name}_ha_cap_df_jp.csv", index=False)
            cs.logger.info("Successfully saved temporary ha_cap_df for %s.", char_name.upper())
        except:
            cs.logger.info("No high_armor_cap_df to save for %s.", char_name.upper())
            pass
        
        character_count += 1

    final_raw_abilities_df = pd.concat(ability_df_list)

    final_raw_abilities_df.to_csv(cs.config['datasets_dir'] + 'raw_abilities.csv', index=False)

    final_raw_bt_effects_df = pd.concat(bt_effect_df_list)

    final_raw_bt_effects_df.to_csv(cs.config['datasets_dir'] + 'raw_bt_effects.csv', index=False)

    final_raw_ha_caps_df = pd.concat(ha_cap_df_list)

    final_raw_ha_caps_df.to_csv(cs.config['datasets_dir'] + 'raw_high_armor_caps.csv', index=False)
    
if __name__ == '__main__':
    main()