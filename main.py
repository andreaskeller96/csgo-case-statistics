import requests
import json
from Crypto.PublicKey import RSA
import time
import datetime

import pandas as pd

from bs4 import BeautifulSoup

import pyperclip

import getpass

from util.crypto import encrypt_data
from util.html_tools import get_variable_from_html, get_json_variable_from_html


def create_steam_auth_session():
    session = requests.Session()
    response = session.get("https://steamcommunity.com/login/home/?goto=")
    user = input("Steam Username:")
    password = getpass.getpass("Password:")
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
    m_gidCaptcha = "-1"
    captchaText = ""
    m_steamidEmailAuth = ""
    m_unRequestedTokenType = "-1"
    login_params = {
        "donotcache":round(time.time() * 1000),
        "password":encrypted_password,
        "username":user,
        "twofactorcode": twofactorcode,
        "emailauth":"",
        "loginfriendlyname":"",
        "captchagid":m_gidCaptcha,
        "captcha_text":captchaText,
        "emailsteamid":m_steamidEmailAuth,
        "rsatimestamp":responseJSON["timestamp"],
        "remember_login": 'false',
        "tokentype": m_unRequestedTokenType
        
    }
    
    header = {
        "Content-Type":"application/x-www-form-urlencoded; charset=UTF-8",
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36"
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

    if not require_email and not require_twofactor:
        print("Session could not be established, wrong password or username")
        exit(-1)
    
    if require_twofactor:
        twofactorcode = input("Enter your 2FA code:")
        login_params["twofactorcode"] = twofactorcode
    else:
        email_code = input("Enter your email confirmation code:")
        login_params["emailauth"] = email_code

    response = session.post("https://steamcommunity.com/login/home/dologin",
                 data = login_params
                 )
    responseJSON = json.loads(response.text)
    if responseJSON["success"] == True:
        return session
    else:
        print("Login failed")
        print(responseJSON)
    
def create_inventory_history_list(html_string):
    soup = BeautifulSoup(html_string, 'html.parser')
    history_list = []
    rows = soup.find_all("div", "tradehistoryrow")
    for row in rows:
        history_element = {
            "description": "",
            "timestamp": None,
            "new_items": [],
            "lost_items": [],
        }
        date = row.find("div", "tradehistory_date").text.strip().split("\t")
        date = [x for x in date if x]
        day = int(date[0].split(" ")[0])
        month = date[0].split(" ")[1][:-1]
        year = int(date[0].split(" ")[-1])
        hour = int(date[1].split(":")[0])
        minute = int(date[1].split(":")[1][:-2])
        ampm = date[1][-2:]
        history_element["timestamp"] = time.mktime(datetime.datetime.strptime(f"{day:02d}/{month}/{year} {hour:02d}:{minute:02d} {ampm}", "%d/%b/%Y %H:%M %p").timetuple())
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
        
        history_list.append(history_element)
    return history_list

def get_inventory_history(session):
    print("Fetching Inventory History")
    response = session.get("https://steamcommunity.com/")
    if response.status_code != 200:
        return None
    steamid = get_variable_from_html("g_steamID", response.text)
    response = session.get(f"https://steamcommunity.com/profiles/{steamid}/inventoryhistory/?app[]=730")
    if response.status_code != 200:
        return None
    profile_link = get_variable_from_html("g_strProfileURL", response.text).replace("\\", "")
    sessionid = get_variable_from_html("g_sessionID", response.text)
    filter_apps = get_variable_from_html("g_rgFilterApps", response.text)


    cursor = get_variable_from_html("g_historyCursor", response.text)
    item_json = get_json_variable_from_html("g_rgDescriptions", response.text)

    full_site = response.text
    item_dict = item_json["730"]
    history = create_inventory_history_list(full_site)

    while True:
        print(f"\rCurrently registered {len(history)} inventory changes", end="")
        req_data = {
            "ajax": "1",
            "sessionid": sessionid,
        }
        for key in cursor:
            req_data[f"cursor[{key}]"] = cursor[key]
        for num, app in enumerate(filter_apps):
            req_data[f"app[{num}]"] = app
        response = session.get(profile_link+"/inventoryhistory/", params=req_data)
        if response.status_code != 200:
            print("")
            for i in range(40, 0, -1):
                print(f"\rWaiting for {i} seconds due to rate limit", end="")
                time.sleep(1)
            print("\rContinuing")
            continue
        response_JSON = json.loads(response.text)
        if "html" in response_JSON:
            history += create_inventory_history_list(response_JSON["html"])
        if "descriptions" in response_JSON:
            item_dict = {**item_dict, **response_JSON["descriptions"]["730"]}
        if "cursor" in response_JSON.keys():
            cursor = response_JSON["cursor"]
        else:
            break  
    return history, item_dict

def get_case_stats(inventory_history, item_json):
    df = pd.DataFrame(inventory_history)
    df["time"] = pd.to_datetime(df['timestamp'],unit='s')
    #df.drop(["timestamp"], inplace=True)
    case_openings = df[df["description"]=="Unlocked a container"]
    drops = df[df["description"]=="Got an item drop"]
    drops = drops.assign(item_name= drops["new_items"].map(lambda x: item_json[f'{x[0]["data-classid"]}_{x[0]["data-instanceid"]}']["market_name"]))
    drops = drops.assign(item_rarity = drops["new_items"].map(lambda x: next(item["name"] for item in item_json[f'{x[0]["data-classid"]}_{x[0]["data-instanceid"]}']["tags"] if item["category"] == "Rarity")))

    case_openings = case_openings.assign(new_item_name = case_openings["new_items"].map(lambda x: item_json[f'{x[0]["data-classid"]}_{x[0]["data-instanceid"]}']["market_name"]))
    case_openings = case_openings.assign(case_name = case_openings["lost_items"].map(lambda x: next(item for item in [ item_json[f'{it["data-classid"]}_{it["data-instanceid"]}']["market_name"] for it in x] if "Key" not in item)))
    case_openings = case_openings.assign(new_item_rarity = case_openings["new_items"].map(lambda x: next(item["name"] for item in item_json[f'{x[0]["data-classid"]}_{x[0]["data-instanceid"]}']["tags"] if item["category"] == "Rarity")))

    weapon_cases = case_openings[~case_openings["new_item_name"].str.contains("Sticker")]
    weapon_cases = weapon_cases[~weapon_cases["case_name"].str.contains("Pins")]
    weapon_cases = weapon_cases[~weapon_cases["case_name"].str.contains("Graffiti")]
    weapon_cases = weapon_cases[~weapon_cases["case_name"].str.contains("Patch")]
    weapon_cases = weapon_cases[~weapon_cases["case_name"].str.contains("Souvenir")]

    return weapon_cases, drops

def print_case_stats(cases):
    ret_string = ""
    ret_string += f"Total amount of cases opened: {len(cases.index)}\n"
    ret_string += "\n"
    #for case_type in cases["case_name"].unique():
    #    ret_string += f'{case_type}: {len(cases[cases["case_name"]==case_type])}\n'

    ret_string += (f'Knives: {len(cases[cases["new_item_name"].str.contains("★")])}\n')
    weapon_cases_noknife = cases[~cases["new_item_name"].str.contains("★")]
    ret_string += (f'Covert: {len(weapon_cases_noknife[weapon_cases_noknife["new_item_rarity"].str.contains("Covert")])}\n')
    ret_string += (f'Classified: {len(cases[cases["new_item_rarity"].str.contains("Classified")])}\n')
    ret_string += (f'Restricted: {len(cases[cases["new_item_rarity"].str.contains("Restricted")])}\n')
    ret_string += (f'Mil-Spec Grade: {len(cases[cases["new_item_rarity"].str.contains("Mil-Spec Grade")])}\n')

    return ret_string

def main():
    session = create_steam_auth_session()
    inventory_history, item_json = get_inventory_history(session)
    cases, drops = get_case_stats(inventory_history, item_json)
    stats_string = print_case_stats(cases)
    print(stats_string)
    clippy = input("Do you want to copy the results to clipboard?: ")
    if clippy == "yes" or clippy=="y":
        pyperclip.copy(stats_string)
    exit()

if __name__ == "__main__":
    main()