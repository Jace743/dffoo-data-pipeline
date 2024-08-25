# DFFOO Data Pipeline
The purpose of this Web Scraping and ETL project was to help Dissidia Final Fantasy Opera Omnia (DFFOO) players understand characters' strength and weaknesses and create better teams. In the game itself, information about each character was provided in a format that wasn't very conducive to quickly understanding and comparing characters, so this project was going to solve that issue. 

***Please Note:** I have made this repo public in order to critique my past code and design, as well as discuss how I would do things differently now that I'm more experienced. While my critique of the code below provides insight into my current skill level, the code itself **does not**. For a more recent example of my Python code and data work, I recommend checking out my [Monte Carlo simulator for Final Fantasy 7 Ever Crisis](https://github.com/Jace743/ever-crisis-gacha-simulator).*

*The current project's development has ended, as the game for which it was created is no longer playable.*

### Project Tech Stack:
- Python (web scraping via `selenium` and some preliminary data modeling using `pandas`; Extraction and Transformation)
- Postgres (for storing the scraped data; Load)
- Data Build Tool (dbt; for data modeling; more Transformation)

### Project goals were: 

1. Scrape character data from one of the game's fan-made websites ([Dissidia Compendium](https://dissidiacompendium.com/), which contained data extracted from the game itself)
   - All of the code for this goal is in `web_scraper.py` (spoiler alert: all the code being in one file is something I'd *definitely* change)
2. Load the data into a Postgres database
   - Code for this goal is also contained in the `web_scraper.py` module
3. Model the data using data build tool (dbt)
   - This was the last step I reached before needing to pause development
   - The `dffoo_analyzer` folder contains the dbt project
4. Create Streamlit dashboards to visualize character qualities

I had to pause development of this project in August 2023, as I was already working full time as a data scientist and analytics engineer and had some big life changes happening at the time. Sadly, before I was ready to resume this project's development, DFFOO announced its end of service, meaning the game is no longer playable. 

# Critiquing my Execution of this Project

## 1. `web_scraper.py` functions/methods are *way* too long

Smaller pieces of code are often easier to read, test, and debug. However, there are functions in `web_scraper.py` that are several hundred lines long! 

At the time of writing this README, it's been over a year since I wrote the original code. So, I'm able to view it with a fresh set of eyes. I can tell that each function is trying to accomplish one goal, but the functions are completing a lot of subtasks that should be extracted into their own functions. For example, when I look at the `generate_ability_dict` method, I can see that the method is:

1. Checking whether the character exists in the targeted game version (characters would often be added to the games Japanese version before the version played by the rest of the world, also known as the Global version)
2. Scrolling through the character's ability page to make sure the scraper has access to all of the character's abilities. The website used lazy loading, so I would need to make sure I loaded everything on the page before extracting data
3. Extracting the text of the each ability
4. Extracting the attributes of each ability (e.g., whether it was a physical attack, magic attack, etc.)
5. Entering this information into a dictionary in one of the scraper's class attributes

Extracting this into separate functions would make the code far more readable. Also, if we hit an error, it'd be much easier to jump into a smaller, appropriately-named function to see what went wrong.

## 2. Some aspects of `CompendiumScraper` should be their own class

Continuing from the previous point, I extract a lot of information about character "abilities." Immediately, I see that a character ability should be its own class, as it's an important entity with its own qualities (e.g., an ability has a description, a number of attacks, attributes, a corresponding character, etc.). Making it is own class would also help with code organization, as any functions related to processing an ability (e.g., parsing info from that ability's HTML) could be nested within it, as opposed to hanging loosely inside a single method of the Scraper class. I'd also place this new class into its own module, which would help readers understand what's needed solely for that class.

## 3. The web scraper has no orchestration

As it stands, `web_scraper.py` handles scraping, some light data modeling, and loading of data into Postgres all in one script. It does this for ~150 characters, one at a time. For some characters, it needed to complete these steps more than once, since a character may have been updated in the Japanese version of the game, but it may not have yet received that update in the Global version. 

If you're an experienced data professional, you can already feel the pain coming -- if anything went wrong for any character at any time during this multi-hour process, everything stopped and had to be started over. The scraper would never reach the step where data was loaded.

A few changes could make this headache vastly smaller:

1. **Scraping data for one character should be one job.** If it succeeds, that character's data should be written to disk, and that job should be over. If it fails, the program should note the failure and move to the next step that doesn't depend on that failing character's data.
   - Taking this a step further, scraping data for one version of one character should be one job.
   - If you take a look at the `/datasets/temp/` directory and lines 1,203 through 1,222 of `web_scraper.py` (such a long file... yikes...), you can see that I had somewhat of an idea of this back then, as I was saving each character's data as the program progressed. However, since everything was still in one script, I would need to check logs or file metadata to see where the scraper failed, and I would probably need to do some tinkering with the scraper to have it start in the proper spot. I'm honestly exhausted just thinking about it.
2. **Uploading data for one character should be one job.** If a character's data is successfully scraped, ingesting that character's data into Postgres should be the next job in the DAG for that character.
   - Scraping for one character is not dependent on whether the scraping for a different character succeeds. 
3. **Data modeling in dbt could be added to this orchestration.** Right now, I would need to manually run `dbt run` in order for my dbt project to build. However, there's no reason not to just include `dbt run` as one of the jobs in my orchestation once all scrapes and ingests have succeeded.

I could probably use Dagster for this orchestration.

## 4. Documentation and Type Hints

Although I have docstrings in `web_scraper.py`, I've since progressed to using [AutoDocstring](https://marketplace.visualstudio.com/items?itemName=njpwerner.autodocstring) both at work and in my personal projects, and it's made a world of difference for people reading my code and for future me reading my code. In this case, it would make understanding my functions' parameters much easier.

As for type hints, you can already see in `web_scraper.py` that I was trying to solve the same problems as type hints, as I would often include the object type in my variable names (e.g., frequently ending my variable names with `_df` or `_dict`). Nowadays, I add type hints when defining new variables, functions, function parameters, and really anything that I can. Future me is usually very grateful that I did so. 

## 5. `Replace` instead of `Append` during Postgres Load/Ingest

I have a pretty good guess as to why I originally chose `if_exists='append'` instead of `if_exists='replace'` when ingesting my data into Postgres (see lines 1,325 through 1,329 of `web_scraper.py`) -- I wanted to keep a record of any changes. However, that could've been solved by using the `Replace` strategy and generating [dbt snapshots](https://docs.getdbt.com/docs/build/snapshots) from the source tables, instead of letting the size of my source tables balloon out of control and having to always filter to the data of the most recent ingest. 

## 6. Add Tests!

I thought about doing some testing that involved the scraping of specific characters and making sure their dataframes came out as expected. The nice thing about scraping data for these characters was that, as an experienced player of the game, I knew *exactly* how everything should look, which allowed me to pick a couple of more complex characters (see `character_ability_test_cases`). However, I didn't take advantage any testing frameworks like `pytest` or implement any continuous integration via Github Actions. 

## 7. Other small changes

There are a couple of other small things that I would change throughout my code, since I've become more proficient with Python:

1. **At the very least, log the exception.** I know that `except Exception` is generally bad practice in Python, but while writing the web scraper, I took bad practice a step further and just... didn't log the exception at all, desipte using logging! While the ideal solution would be to specify different exceptions and only use a broad `except Exception` as a last resort, I at least could have used `except Exception as e:` and added the exception to my logging statement.
2. **If possible, remove hard-coded rules.** In line 1,1777 of `web_scraper.py`, I begin an `if` statement that's meant to restart Selenium's chrome driver after scraping every 30 game characters to prevent the driver from crashing. My guess is that, at the time, I thought it would be a long while before there were 180 characters in the game, as the developers were releasing about 1 new character a month, if that. So, I hard coded a list of integer values counting by 30 up to 180 for this purpose. Reading it now, I could have made this rule dynamic by writing `if (character_count % 30) == 0:` instead of using the hard coded list.
3. **Make it a Python package.** This is a Python project, and it should be structured as such.
