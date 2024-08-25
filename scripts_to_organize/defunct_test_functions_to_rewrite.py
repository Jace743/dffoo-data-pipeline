    # def generate_test_case_ability_dfs(self, list_of_character_names, JP=False):
    #     """
    
    #     Save out characters whose HP attack counts we're confident in. We can then use these
    #     test cases to see whether we've broken a previous character's df when we make changes.
    
    #     """
    
    #     for t_case in list_of_character_names:
    #         df = self.extract_ability_hp_attack_count(t_case, JP=JP)
    
    #         print(t_case.upper(), "test case df")
        
    #         df.to_csv(
    #             f"C:\\Users\\jasre\\Code\\dffoo-data-pipeline\\character_ability_test_cases\\{t_case}_ability_df.csv",
    #             index = False
    #         )

    # def test__recent_changes_have_not_altered_previous_ability_dfs(self, list_of_character_names, JP=False):
    #     """
    
    #     Compares a newly-generated ability df to one that was generated in the past to see if
    #     recent changes have broken functionality for a previously-completed character.
    
    #     Accepted characters for now: 
    #         ['auron', 'sherlotta', 'aerith', 'lenna', 'warrioroflight', 'astos', 'paine']
    
    #     """
        
    #     broken_characters_list = []
        
    #     for t_case in list_of_character_names:
    #         new_df = self.extract_ability_hp_attack_count(t_case, JP=JP)
    
    #         try:
    #             old_df = pd.read_csv(
    #                 f"C:\\Users\\jasre\\Code\\dffoo-data-pipeline\\character_ability_test_cases\\{t_case}_ability_df.csv"
    #             )
    #         except:
    #             print(f"Could not load a previous ability_df for {t_case.title()}.")
    #             print("Are you sure one was previously generated?")
    
    #             continue
    
    #         if len(old_df.compare(new_df)) > 0:
    #             broken_characters_list.append(t_case)
    
    #     if len(broken_characters_list) > 0:
    #         print("Broken ability_dfs were found.\n Returning list of characters to review.")
    #         return broken_characters_list
    #     else:
    #         print("No broken ability_dfs!")
