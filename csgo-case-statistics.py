import requests, json, time, datetime, math, pyperclip, pickle, getpass, os
import pandas as pd


from Crypto.PublicKey import RSA
from bs4 import BeautifulSoup
from util.crypto import encrypt_data
from util.html_tools import get_variable_from_html, get_json_variable_from_html


def create_steam_auth_session(user=None, password=None, captcha=None, captcha_gid=None):
    
    session = requests.Session()
    response = session.get("https://steamcommunity.com/login/home/?goto=")
    
    if user is None:
        user = input("Steam Username: ")
    cookiefile = f"steam_sessioncookie_{user}.pkl"

    if os.path.isfile(cookiefile):
        with open (cookiefile, "rb") as f:
            session.cookies.update(pickle.load(f))
        test_login = session.get("https://steamcommunity.com/")
        steamid = get_variable_from_html("g_steamID", test_login.text)
        #Check if the session is still valid
        if not steamid is None and steamid.isnumeric():
            print("Resuming previous session")
            return session

    if password is None:
        password = getpass.getpass("Password: ")
    login_params = {
        "username": user
    }

    response = session.post("https://steamcommunity.com/login/home/getrsakey/",
        params = login_params)
    responseJSON = json.loads(response.text)
    
    
    exp = int(responseJSON["publickey_exp"],16)
    mod = int(responseJSON["publickey_mod"],16)
    
    rsa_key = RSA.construct((mod, exp))
    
    encrypted_password = encrypt_data(password, rsa_key)
    
    twofactorcode = ""
    gidCaptcha = "-1"
    captchaText = ""
    if captcha is not None:
        captchaText = captcha
    if captcha_gid is not None:
        gidCaptcha = captcha_gid
    m_steamidEmailAuth = ""
    m_unRequestedTokenType = "-1"
    login_params = {
        "donotcache":round(time.time() * 1000),
        "password":encrypted_password,
        "username":user,
        "twofactorcode": twofactorcode,
        "emailauth":"",
        "loginfriendlyname":"",
        "captchagid":gidCaptcha,
        "captcha_text":captchaText,
        "emailsteamid":m_steamidEmailAuth,
        "rsatimestamp":responseJSON["timestamp"],
        "remember_login": 'false',
        "tokentype": m_unRequestedTokenType
        
    }
    
    
    response = session.post("https://steamcommunity.com/login/home/dologin",
                     data = login_params
                     )
    responseJSON = json.loads(response.text)

    if responseJSON["success"] == True:
        print(f"Successfully logged in {user}")
        return session

    require_twofactor = False
    require_email = False
    if "requires_twofactor" in responseJSON:
        if responseJSON["requires_twofactor"] == True:
            require_twofactor = True
    if "emailauth_needed" in responseJSON:
        if responseJSON["emailauth_needed"] == True:
            require_email = True
    
    require_captcha = False

    if "captcha_needed" in responseJSON:
        if responseJSON["captcha_needed"] == True:
            require_captcha = True

    if require_captcha:
        print("Steam requests a captcha, this is currently not implemented!")
        return None
        print("You need to solve this captcha first:")
        print(f"https://steamcommunity.com/login/rendercaptcha/?gid={responseJSON['captcha_gid']}")
        captcha = input("Enter the solution to the captcha: ")
        return create_steam_auth_session(user=user, password=password, captcha=captcha, captcha_gid=responseJSON['captcha_gid'])

        

    if not require_email and not require_twofactor:
        print("Session could not be established, wrong password or username")
        print(responseJSON)
        return None
    
    if require_twofactor:
        twofactorcode = input("Enter your 2FA code: ")
        login_params["twofactorcode"] = twofactorcode
    if require_email:
        email_code = input("Enter your email confirmation code: ")
        login_params["emailauth"] = email_code

    response = session.post("https://steamcommunity.com/login/home/dologin",
                 data = login_params
                 )
    responseJSON = json.loads(response.text)
    if responseJSON["success"] == True:
        with open(cookiefile, "wb") as f:
            pickle.dump(session.cookies, f)
        return session
    else:
        print("Login failed")
        print(responseJSON)

def create_inventory_history_dict(html_string, full_hist):
    soup = BeautifulSoup(html_string, 'html.parser')
    history_dict = {}
    rows = soup.find_all("div", "tradehistoryrow")
    for row in rows:
        history_element = {
            "description": "",
            "timestamp": None,
            "new_items": [],
            "lost_items": [],
        }
        date = row.find("div", "tradehistory_date").text.strip().split("\t")

        date_str = ""
        for element in date:
            date_str+=element
            date_str+= " "
    
        history_element_timestamp = pd.to_datetime(date_str, infer_datetime_format=True).timestamp()
        history_element["timestamp"] = history_element_timestamp
        history_element["description"] = row.find("div", "tradehistory_event_description").text.strip()
        item_changegroups = row.find_all("div", "tradehistory_items tradehistory_items_withimages")
        #print(history_element)
        for item_changegroup in item_changegroups:
            item_type = item_changegroup.find("div", "tradehistory_items_plusminus").text.strip()
            items = item_changegroup.find_all("a", "history_item economy_item_hoverable")
            items += item_changegroup.find_all("span", "history_item economy_item_hoverable")
            item_list = []
            for item in items:
                item_dict = {}
                item_dict["data-classid"] = item["data-classid"]
                item_dict["data-instanceid"] = item["data-instanceid"]
                item_list.append(item_dict)
            if item_type == "+":
                history_element["new_items"] += item_list
            elif item_type == "-":
                history_element["lost_items"] += item_list
        new_name = f"{history_element_timestamp}_{history_element['description']}"
        new_name_actual = new_name
        i=0
        while new_name_actual in history_dict or new_name_actual in full_hist:
            new_name_actual = f"{new_name}_{i}"
            i+=1
        history_dict[new_name_actual] = history_element
    return history_dict

def get_inventory_history(session):
    print("Fetching Inventory History")
    response = session.get("https://steamcommunity.com/")
    if response.status_code != 200:
        print("Steam Community not reachable, check your internet connection and try again")
        return None, None
    steamid = get_variable_from_html("g_steamID", response.text)
    if steamid is None:
        print("Steam Session failure")
        return None, None
    need_status_file = True
    steamid_status = {}
    #Check if we fetched this data before and have it stored
    if os.path.isfile(f"{steamid}_status.json"):
        with open (f"{steamid}_status.json", "r") as f:
            try:
                steamid_status = json.load(f)
            except:
                steamid_status = {}
        if "newest_timestamp" in steamid_status and "complete_history" in steamid_status and "oldest_timestamp" in steamid_status:
            need_status_file = False
    #create new status file
    if need_status_file:
        steamid_status = {}
        steamid_status["newest_timestamp"] = 0
        steamid_status["complete_history"] = False
        steamid_status["oldest_timestamp"] = 0
        with open(f"{steamid}_status.json", "w") as f:
            json.dump(steamid_status, f)

    response = session.get(f"https://steamcommunity.com/profiles/{steamid}/inventoryhistory/?app[]=730&l=english")
    if response.status_code != 200:
        print("Steam returned an error when trying to access inventory history, trying again in 5s")
        time.sleep(5)
        return get_inventory_history(session)
    profile_link = get_variable_from_html("g_strProfileURL", response.text)
    sessionid = get_variable_from_html("g_sessionID", response.text)
    filter_apps = get_variable_from_html("g_rgFilterApps", response.text)


    cursor = get_variable_from_html("g_historyCursor", response.text)
    item_json = get_json_variable_from_html("g_rgDescriptions", response.text)

    if None in [profile_link, sessionid, filter_apps, cursor, item_json]:
        return None, None

    profile_link = profile_link.replace("\\", "")
    
    full_site = response.text
    item_dict = item_json["730"]
    try:
        history = create_inventory_history_dict(full_site, {})
    except:
        return None, None
    
    cur_timestamp = math.floor(time.time())
    
    history_file = f"{steamid}_history.pkl"
    dict_file = f"{steamid}_dict.pkl"
    #Continue an incomplete history
    incremental_load = False
    if steamid_status["complete_history"]==True and os.path.isfile(history_file) and os.path.isfile(dict_file):
        incremental_load = True
        with open(history_file, "rb") as f:
            old_history = pickle.load(f)
        with open(dict_file, "rb") as f:
            old_item_dict = pickle.load(f)
        history = {**old_history, **history}
        item_dict = {**old_item_dict, **item_dict}
        #save current state to files
        with open(history_file, "wb") as f:
            pickle.dump(history, f)
        with open(dict_file, "wb") as f:
            pickle.dump(item_dict, f)
        with open(f"{steamid}_status.json", "w") as f:
            json.dump(steamid_status, f)
    elif steamid_status["complete_history"]==False and steamid_status["oldest_timestamp"] != 0 and os.path.isfile(history_file) and os.path.isfile(dict_file):
        print("Resuming interrupted fetch")
        cursor["time"] = steamid_status["oldest_timestamp"]
        with open(history_file, "rb") as f:
            history = pickle.load(f)
        with open(dict_file, "rb") as f:
            item_dict = pickle.load(f)

    while True:
        print(f"\rCurrently registered {len(history)} inventory changes", end="")
        cursor_timestamp = cursor["time"]
        #Nothing new to fetch
        if incremental_load and cursor_timestamp < steamid_status["newest_timestamp"]:
            break
        req_data = {
            "ajax": "1",
            "l": "english",
            "sessionid": sessionid,
        }
        for key in cursor:
            req_data[f"cursor[{key}]"] = cursor[key]
        for num, app in enumerate(filter_apps):
            req_data[f"app[{num}]"] = app
        response = session.get(profile_link+"/inventoryhistory/", params=req_data)

        rate_limited = (response.status_code != 200)

        if not rate_limited:
            try:
                response_JSON = json.loads(response.text)
            except:
                rate_limited = True

        if rate_limited:
            print("")
            for i in range(40, 0, -1):
                print(f"\rWaiting for {i:02d} seconds due to steam rate limit", end="")
                time.sleep(1)
            print("\r                                                                 ", end="")
            print("\rContinuing")
            continue

        if "html" in response_JSON:
            try:
                additional_history = create_inventory_history_dict(response_JSON["html"], history)
            except:
                continue
            history = {**history,  **additional_history}
        if "descriptions" in response_JSON:
            if "730" in response_JSON["descriptions"]:
                item_dict = {**item_dict, **response_JSON["descriptions"]["730"]}
        if "cursor" in response_JSON:
            cursor = response_JSON["cursor"]
            if "time" in cursor:
                steamid_status["oldest_timestamp"] = cursor["time"]
        else:
            break
        #save current state to files
        with open(history_file, "wb") as f:
            pickle.dump(history, f)
        with open(dict_file, "wb") as f:
            pickle.dump(item_dict, f)
        with open(f"{steamid}_status.json", "w") as f:
            json.dump(steamid_status, f)
    steamid_status["complete_history"] = True
    steamid_status["newest_timestamp"] = cur_timestamp
    with open(f"{steamid}_status.json", "w") as f:
            json.dump(steamid_status, f)

    print("\nFinished fetching Inventory History\n")
    return history, item_dict

def get_item_name(x, item_json):
    if "data-classid" not in x[0] or "data-instanceid" not in x[0]:
        return "Unknown"
    class_instance = f'{x[0]["data-classid"]}_{x[0]["data-instanceid"]}'
    if class_instance in item_json:
        if "market_name" in item_json[class_instance]:
            return item_json[class_instance]["market_name"]
        else:
            return class_instance
    else:
        return class_instance

def get_item_rarity(x, item_json):
    if "data-classid" not in x[0] or "data-instanceid" not in x[0]:
        return "Unknown"
    class_instance = f'{x[0]["data-classid"]}_{x[0]["data-instanceid"]}'
    if class_instance in item_json:
        return next(item["name"] for item in item_json[class_instance]["tags"] if item["category"] == "Rarity")
    else:
        return class_instance

def get_case_name (x, item_json):
    if "data-classid" not in x[0] or "data-instanceid" not in x[0]:
        return "Unknown"
    class_instance = f'{x[0]["data-classid"]}_{x[0]["data-instanceid"]}'
    
    if class_instance in item_json:
        return next(item for item in [ item_json[class_instance]["market_name"] for it in x] if "Key" not in item)
    else:
        return class_instance

def get_case_stats(inventory_history, item_json):
    df = pd.DataFrame(inventory_history.values())
    df["time"] = pd.to_datetime(df['timestamp'],unit='s')
    #df.drop(["timestamp"], inplace=True)
    case_openings = df[df["description"]=="Unlocked a container"]
    drops = df[df["description"]=="Got an item drop"]
    drops = drops.assign(item_name= drops["new_items"].map(lambda x: item_json[f'{x[0]["data-classid"]}_{x[0]["data-instanceid"]}']["market_name"]))
    drops = drops.assign(item_rarity = drops["new_items"].map(lambda x: next(item["name"] for item in item_json[f'{x[0]["data-classid"]}_{x[0]["data-instanceid"]}']["tags"] if item["category"] == "Rarity")))

    case_openings = case_openings.assign(new_item_name = case_openings["new_items"].map(lambda x: get_item_name(x, item_json)))
    case_openings = case_openings.assign(case_name = case_openings["lost_items"].map(lambda x: get_case_name(x, item_json)))
    case_openings = case_openings.assign(new_item_rarity = case_openings["new_items"].map(lambda x: get_item_rarity(x, item_json)))

    weapon_cases = case_openings[~case_openings["new_item_name"].str.contains("Sticker")]
    weapon_cases = weapon_cases[~weapon_cases["case_name"].str.contains("Pins")]
    weapon_cases = weapon_cases[~weapon_cases["case_name"].str.contains("Graffiti")]
    weapon_cases = weapon_cases[~weapon_cases["case_name"].str.contains("Patch")]
    weapon_cases = weapon_cases[~weapon_cases["case_name"].str.contains("Souvenir")]

    return weapon_cases, drops

def print_case_stats(cases):
    ret_string = ""
    total_case_count = len(cases.index)
    ret_string += f"Total amount of cases opened: {total_case_count}\n"
    if total_case_count==0:
        return ret_string
    #ret_string += "\n"
    #for case_type in cases["case_name"].unique():
    #    ret_string += f'{case_type}: {len(cases[cases["case_name"]==case_type])}\n'

    weapon_cases_noknife = cases[~cases["new_item_name"].str.contains("★")]

    knive_count = len(cases[cases["new_item_name"].str.contains("★")])
    red_count = len(weapon_cases_noknife[weapon_cases_noknife["new_item_rarity"].str.contains("Covert")])
    pink_count = len(cases[cases["new_item_rarity"].str.contains("Classified")])
    purple_count = len(cases[cases["new_item_rarity"].str.contains("Restricted")])
    blue_count = len(cases[cases["new_item_rarity"].str.contains("Mil-Spec Grade")])

    ret_string += (f'Knives:         {knive_count: =5d} ({(knive_count/total_case_count)*100: =6.2f}%) - Odds:  0.26%\n')
    ret_string += (f'Covert:         {red_count: =5d} ({(red_count/total_case_count)*100: =06.2f}%) - Odds:  0.64%\n')
    ret_string += (f'Classified:     {pink_count: =5d} ({(pink_count/total_case_count)*100: =06.2f}%) - Odds:  3.20%\n')
    ret_string += (f'Restricted:     {purple_count: =5d} ({(purple_count/total_case_count)*100: =06.2f}%) - Odds: 15.98%\n')
    ret_string += (f'Mil-Spec Grade: {blue_count: =5d} ({(blue_count/total_case_count)*100: =06.2f}%) - Odds: 79.92%\n')

    return ret_string

def print_coverts(cases):
    knives = cases[cases["new_item_name"].str.contains("★")]
    weapon_cases_noknife = cases[~cases["new_item_name"].str.contains("★")]
    coverts = weapon_cases_noknife[weapon_cases_noknife["new_item_rarity"].str.contains("Covert")]

    ret_string = ""

    ret_string += ("Knives:\n")
    for index, row in knives.iterrows():
            ret_string += (f'Opened {row["new_item_name"]} on {row["time"]}\n') 
        
    ret_string += ("Coverts:\n")

    for index, row in coverts.iterrows():
            ret_string += (f'Opened {row["new_item_name"]} on {row["time"]}\n') 
    
    return ret_string


def main():
    #Create Steam Authenticated Session
    session = create_steam_auth_session()
    if session is None:
        return -1
    #Download the complete history
    inventory_history, item_json = get_inventory_history(session)
    if None in [inventory_history, item_json]:
        print("Error while fetching History")
        return -1
    #Process the history into dataframes
    cases, drops = get_case_stats(inventory_history, item_json)
    #Print the results to console
    stats_string = print_case_stats(cases)
    print(stats_string)
    clippy = input("Do you want to copy the results to clipboard?: ")
    if clippy == "yes" or clippy=="y":
        pyperclip.copy(stats_string)

    if len(cases[cases["new_item_rarity"].str.contains("Covert")])>0:
        covs = input("Do you want to print the coverts to console?: ")
        covert_string = print_coverts(cases)
        if covs == "yes" or covs=="y":
            print(covert_string)
            clippy = input("Do you want to copy the coverts to clipboard?: ")
            if clippy == "yes" or clippy=="y":
                pyperclip.copy(covert_string)

    save = input("Do you want to save your case opening history as csv?: ")
    if save == "yes" or save=="y":
        cases_saving = cases[["time", "new_item_name", "case_name", "new_item_rarity"]]
        cases_saving = cases_saving.rename(columns={"new_item_name": "Weapon", "case_name": "Case", "new_item_rarity": "Rarity"}, errors="ignore")
        cases_saving.set_index("time",inplace=True)

        cases_saving.to_csv(f"{int(time.time())}_case_rewards.csv")

if __name__ == "__main__":
    main()
    input("Press enter to exit")