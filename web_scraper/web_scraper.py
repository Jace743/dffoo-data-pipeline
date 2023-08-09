import pandas as pd
import time
import re
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
    
    def __init__(self):
        self.chars_with_reworks_pending = []
        self.character_list_url = 'https://dissidiacompendium.com/characters/?'

        self.driver = webdriver.Chrome()

        self.generate_character_links()
    
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

    def generate_ability_dict(
        self,
        char_name,  # Character name, as a string
        scroll_speed = 1000,  # Scrolling speed to move through the page for lazy loading
        verbose = False  # If true, will return print statements on iterations
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
    
        try:
            self.driver.get(self.character_dict_omnibus[char_name]['abilities_url'])
        except:
            print("You need to generate the character_dict_omnibus first (run generate_character_links).")
            return
    
        time.sleep(5)
        
        self.screen_for_rework(char_name)

        try:
            list_build_complete = False
            
            count = 0
            
            while list_build_complete == False:
                
                self.driver.execute_script(f"window.scrollBy(0, {scroll_speed});")
                time.sleep(1)
                ability_list = self.driver.find_elements(By.XPATH, "//div[@class='infotitle abilitydisplayfex ']")
                
                # The last two abilities are calls. So, the second to last ability should be a call when we're done.
                match = re.search('\(C\)', ability_list[-2].text)
                list_build_complete = True if match else False
                
                if verbose:
                    print(f"This iteration caught {len(ability_list)} abilities.")
                
                    print('-----------')
                count += 1
                if count == 15:
                    print("Too many iterations. Examine this function for:")
                    print(char_name)
                    break
            
            if verbose:
                print(f"This took {count} iterations.\n")
            
                for ability in ability_list:
                    print(ability.text)
        
            ability_info_list = self.driver.find_elements(By.XPATH, "//div[@class='bluebase abilityinfobase']")
        
            if verbose:
                print(f"Collected ability info list")
            
            ability_dict = {}
            
            count = 0
            
            for ability in ability_list:
                ability_name = str(ability_list[count].text.split(' - ')[0])
                
                ability_dict[ability_name] = ability_info_list[count]
                count += 1
        
            if verbose:
                print('Added char name to ability dict')
            
            return ability_dict
        except:
            print("Unable to access abilities for a character. Maybe not on GL yet.")
            return None

    def prettify_html_to_list(self, html_element):
        """
    
        Retrieves the 'outerHTML' attribute of an HTML element, parses it, and  
        returns a list to enable iteration over the HTML element.
    
        """
        
        soup = BeautifulSoup(html_element.get_attribute('outerHTML'), 'lxml')
    
        return [line for line in soup.prettify().split('\n')]

    def extract_ability_hp_attack_count(
        self,
        char_name,  # Character name, as a string
        scroll_speed = 1000,  # Scrolling speed to move through the page for lazy loading
        verbose = False  # If true, will return print statements on iterations
    ):
        """
    
        Extracts the number of HP attacks dealt to an ability's main target and non-targets. The
        function input should be a character name (char_name) in string format. Utilizes the 
        `generate_ability_dict` function.
    
        Returns a pandas dataframe with the ability name, number of HP attacks into main targets, 
        and number of HP attacks into non-targets.
    
        """
    
        ability_dictionary = self.generate_ability_dict(
            char_name = char_name, 
            scroll_speed = scroll_speed, 
            verbose = verbose
        )
        
        df_row_list = []
        
        for ability_name, ability_div in ability_dictionary.items():
        
            if ability_name == 'char_name':
                continue
            
            ability_html_lines = self.prettify_html_to_list(ability_div)
        
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
    
            df_row_list.append(row_dict)
    
        ability_df = pd.DataFrame(df_row_list)

        ability_df['char_name'] = char_name
        
        filtered_df = ability_df[~ability_df['ability_name'].str.contains('(C)', regex = False)].query(
            'main_target_hp_attacks > 0'
        ).reset_index(drop = True)
    
        return filtered_df[['char_name', 'ability_name', 'main_target_hp_attacks', 'non_target_hp_attacks', 'hp_dmg_cap_up_perc']]

    def generate_test_case_ability_dfs(self, list_of_character_names):
        """
    
        Save out characters whose HP attack counts we're confident in. We can then use these
        test cases to see whether we've broken a previous character's df when we make changes.
    
        """
    
        for t_case in list_of_character_names:
            ability_dict = self.generate_ability_dict(self.character_dict_omnibus[t_case]['abilities_url'])
        
            df = self.extract_ability_hp_attack_count(ability_dict)
    
            print(t_case.upper(), "test case df")
        
            df.to_csv(
                f"C:\\Users\\jasre\\Code\\dffoo-data-pipeline\\character_ability_test_cases\\{t_case}_ability_df.csv",
                index = False
            )

    def test__recent_changes_have_not_altered_previous_ability_dfs(self, list_of_character_names):
        """
    
        Compares a newly-generated ability df to one that was generated in the past to see if
        recent changes have broken functionality for a previously-completed character.
    
        Accepted characters for now: 
            ['auron', 'sherlotta', 'aerith', 'lenna', 'warrioroflight', 'astos', 'paine']
    
        """
        
        broken_characters_list = []
        
        for t_case in list_of_character_names:
            new_ability_dict = self.generate_ability_dict(self.character_dict_omnibus[t_case]['abilities_url'])
    
            new_df = self.extract_ability_hp_attack_count(new_ability_dict)
    
            try:
                old_df = pd.read_csv(
                    f"C:\\Users\\jasre\\Code\\dffoo-data-pipeline\\character_ability_test_cases\\{t_case}_ability_df.csv"
                )
            except:
                print(f"Could not load a previous ability_df for {t_case.title()}.")
                print("Are you sure one was previously generated?")
    
                continue
    
            if len(old_df.compare(new_df)) > 0:
                broken_characters_list.append(t_case)
    
        if len(broken_characters_list) > 0:
            print("Broken ability_dfs were found.\n Returning list of characters to review.")
            return broken_characters_list
        else:
            print("No broken ability_dfs!")

    def retrieve_hp_caps_from_bt(
        self,
        char_name,  # Character's name as a string
        verbose = False  # If true, will return print statements
    ):
    
        """
    
        Takes a character's name as input and returns a dictionary with three key-value pairs:
    
        1) Character's name
        2) Personal HP Dmg Cap up from BT effect
        3) Party-side HP Dmg Cap up from BT effect
        
        """
    
        actions = ActionChains(self.driver)
        
        self.driver.get(self.character_dict_omnibus[char_name]['buffs_url'])
        
        time.sleep(5)
        
        bt_personal_hp_dmg_cap_up = 0
        bt_party_hp_dmg_cap_up = 0
        
        try:
            # Find the BT button for the character's buff page
            bt_button_element = self.driver.find_element(By.XPATH, "//li[@class='filterinactive buffbutton wpbtbutton']")
        except:
            print(f"Unable to find a BT for {char_name.title()}. Do they have one in this timeline (GL/JP)?")
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
                    return
        
            initial_x_offset = offset = 80
        
            while width_element.get_attribute('style') != 'width: 100%;':
                offset += 10
                actions.drag_and_drop_by_offset(slider, offset, 0).release().perform()
                if verbose:
                    print(f"Offset of {offset} performed.")
        
            if verbose:
                print("Reached max stacks!")
        except:
            if verbose:
                print(f"No stack slider found. Assuming {char_name} has a BT without stacks.")
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
    
        if verbose:
            print(f"Personal HP Dmg Cap Up: {bt_personal_hp_dmg_cap_up}%")
            print(f"Party HP Dmg Cap Up: {bt_party_hp_dmg_cap_up}%")
    
        bt_effect_dict = {}
        bt_effect_dict['char_name'] = char_name
        bt_effect_dict['bt_personal_hp_dmg_cap_up'] = bt_personal_hp_dmg_cap_up
        bt_effect_dict['bt_party_hp_dmg_cap_up'] = bt_party_hp_dmg_cap_up
    
        return bt_effect_dict

    def retrieve_ha_hp_dmg_cap_up(self, char_name, verbose=False):
        """
    
        Retrieves HP Dmg Cap up values from a character's high armor pages, both personal and 
        party-wide, and returns a dictionary with three keys: 1) character name, 2) personal 
        cap up, and 3) party-wide cap up.
    
        """
        self.driver.get(self.character_dict_omnibus[char_name]['high_armor_url'])
        
        time.sleep(5)
        
        high_armor_html = self.prettify_html_to_list(
            self.driver.find_element(By.XPATH, "//div[@class='infonameholderenemybuff default_passive Buffbase']")
        )
        
        personal_ha_hp_dmg_cap_up = 0
        party_ha_hp_dmg_cap_up = 0
        
        # Extract base high armor values
        for index, line in enumerate(high_armor_html):
            if re.search(r"- MAX BRV Cap", line):
                personal_ha_hp_dmg_cap_up += int(re.search("\d+", high_armor_html[index + 6]).group())
            if re.search(r"- Party MAX BRV Cap", line):
                party_ha_hp_dmg_cap_up += int(re.search("\d+", high_armor_html[index + 6]).group())
        
        if verbose:
            print(f"Personal Cap Up: {personal_ha_hp_dmg_cap_up}")
            print(f"Party Cap Up: {party_ha_hp_dmg_cap_up}")
        
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
        
        if verbose:
            print(f"Personal Cap Up: {personal_ha_hp_dmg_cap_up}")
            print(f"Party Cap Up: {party_ha_hp_dmg_cap_up}")
    
        ha_hp_dmg_cap_up_dict = {}
        ha_hp_dmg_cap_up_dict['char_name'] = char_name
        ha_hp_dmg_cap_up_dict['personal_hp_dmg_cap_up'] = personal_ha_hp_dmg_cap_up
        ha_hp_dmg_cap_up_dict['party_ha_hp_dmg_cap_up'] = party_ha_hp_dmg_cap_up
    
        return ha_hp_dmg_cap_up_dict

    def extract_inline_ability_attributes(
        self,
        char_name, 
        scroll_speed = 1000, 
        verbose = False
    ):
    
        """
    
        Takes a character name and extracts all of the inline attributes of their abilities. Returns
        this information in a dictionary with ability name as keys and a list of inline attributes as
        values.
    
        """
        
        self.driver.get(self.character_dict_omnibus[char_name]['abilities_url'])
        
        time.sleep(5)
        
        list_build_complete = False
        
        count = 0
        
        while list_build_complete == False:
            
            self.driver.execute_script(f"window.scrollBy(0, {scroll_speed});")
            time.sleep(1)
            
            try:
                ability_list = self.driver.find_elements(By.XPATH, "//div[@class='infotitle abilitydisplayfex ']")
                
                # The last two abilities are calls. So, the second to last ability should be a call when we're done.
                match = re.search('\(C\)', ability_list[-2].text)
                list_build_complete = True if match else False
            except:
                print(f"Could not find abilities for {char_name.title()}.")
                return
            
            if verbose:
                print(f"This iteration caught {len(ability_list)} abilities.")
            
                print('-----------')
            count += 1
            if count == 15:
                print(f"Too many iterations. Examine this function for: {char_name.title()}")
                return
        
        ability_attribute_dict = {}
        
        for index, ability_div in enumerate(ability_list):
            inline_attribute_list  = []
            
            ability_name = str(ability_list[index].text.split(' - ')[0])
            
            ability_div_html = self.prettify_html_to_list(ability_div)
        
            for line in ability_div_html:
                if re.search(r"inline ", line):
                    inline_attribute = re.search(r"(inline )(\w+)", line).group(2)
                    inline_attribute_list.append(inline_attribute)
        
            ability_attribute_dict[ability_name] = inline_attribute_list
    
        return ability_attribute_dict
    
    def screen_for_rework(self, char_name):
        """
        
        Checks whether a character has had a rework in the Japanese version of the game. If so, this function
        will add them to the characters with reworks list to be parsed later. 
        
        """

        try:
            if self.driver.find_element(By.XPATH, "//li[@class='filterinactive buffbutton reworktabred_direct']"):
                self.chars_with_reworks_pending.append(char_name)
        except:
            return

