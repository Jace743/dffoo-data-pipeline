import pandas as pd
import time
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


driver = webdriver.Chrome()

character_list_url = 'https://dissidiacompendium.com/characters/?'
driver.get(character_list_url)

try:
    character_link_list = WebDriverWait(
        driver,
        timeout=10  # Wait up to 10 seconds before timing out. 
    ).until(
        EC.presence_of_all_elements_located((By.CLASS_NAME, "characterlink"))
    )
except:
    print("Error during character list extraction. Closing.")
    driver.quit()

character_list = []

for char_link in character_link_list:
    character_list.append(char_link.get_attribute("href").split('/')[-1])

