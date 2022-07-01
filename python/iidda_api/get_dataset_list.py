from functools import cache
import requests
import os
import configparser
from iidda_api import read_config
import json
import aiohttp
import asyncio
from aiohttp_client_cache import CachedSession, FileBackend
import requests_cache
from appdirs import *

async def get_release_list(access_token, cache_config, clear_cache):
    async with CachedSession(cache=cache_config) as session:
        if clear_cache == True or (isinstance(clear_cache,str) and clear_cache.lower() == 'true'):
            await session.cache.clear()
        page = 1
        release_list = []
        while True:
            async with session.get(f"https://api.github.com/repos/{read_config('repository')}/releases?per_page=100&page={page}", headers={"Authorization": "token " + access_token}) as response:
                releases = await response.json()
                if not releases:
                    break
                release_list.extend(list(releases))
                page += 1  
                
        return release_list
        
def get_dataset_list(clear_cache, response_type="metadata"):
    # Get access token
    ACCESS_TOKEN = read_config('access_token')

    headers = {
        'Authorization': 'token ' + ACCESS_TOKEN,
        'Accept': 'application/octet-stream'
    }
    
    # make cache directory
    cache_path = user_cache_dir("iidda-api-cache","")
    print(cache_path)
    if not os.path.isdir(cache_path):
        os.makedirs(cache_path)
    # Cache configurations
    assets_cache = FileBackend(
        cache_name = cache_path
    )
    
    release_list_cache = FileBackend(
        cache_name = cache_path,
    )
        
    releases = asyncio.run(get_release_list(ACCESS_TOKEN,release_list_cache,clear_cache))
    
    dataset_title_list = map(lambda release: release['name'], releases)
        
    dataset_title_list = list(dict.fromkeys(dataset_title_list))
    
    async def main():
        async with CachedSession(cache=assets_cache) as session:
            if clear_cache == True or (isinstance(clear_cache,str) and clear_cache.lower() == 'true'):
                await session.cache.clear()
            tasks = []
            for title in dataset_title_list:
                task = asyncio.ensure_future(get_dataset_data(session, title))
                tasks.append(task)

            dataset_metadata = await asyncio.gather(*tasks)

            result_file = dict(zip(dataset_title_list,dataset_metadata))

            return result_file

    async def get_dataset_data(session,title): 
        # Search for latest version
        title_version_list = filter(lambda release: release['name'] == title, releases)
        title_version_list = sorted(title_version_list, key=lambda release: int(release['body'][8:]))
        latest_version = title_version_list[len(title_version_list) - 1]
        
        # get metadata
        latest_version_metadata = latest_version['assets']
        if response_type == "metadata":
            latest_version_metadata = list(filter(lambda asset: asset['name'] == title + '.json', latest_version_metadata))
        elif response_type == "github_url":
            return {"github_url": latest_version["html_url"]}
        else:
            latest_version_metadata = list(filter(lambda asset: asset['name'] == title + "_" + response_type + '.json', latest_version_metadata))

        if latest_version_metadata != []:
            metadata_url = latest_version_metadata[0]['url']
            async with session.get(metadata_url,headers=headers) as response:
                metadata = await response.text()
                metadata = json.loads(metadata)
                return metadata
        else:
            return 'No metadata.'
            
    # If OS is windows then include the below line
    # asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(main())
