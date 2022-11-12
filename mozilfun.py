from flask import Flask, send_from_directory, send_file, request
from requests import get
import bs4
import re
from os import listdir, makedirs

app = Flask(__name__)

# open template pages. this is done once when program starts
homepage_html = open('html/home.html').read()
query_html_template = open('html/query.html').read()
addon_page_template = open('html/addon.html').read()

# make directory for caches if not exist.
makedirs('addons', exist_ok=True)
makedirs('cache', exist_ok=True)

# route for homepage
@app.route('/')
def get_home():
    return homepage_html

# route for downloading images and other files in mozilla addons site.
# p stands for proxy
@app.route('/p/<path:path>')
def proxy_data(path):
    # download file from mozilla into cache folder
    download_link = 'https://addons.mozilla.org/' + path
    file_name = 'cache/' + download_link.replace('/', '_')
    with get(download_link, stream=True) as r:
        r.raise_for_status()
        with open(file_name, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192): 
                f.write(chunk)
    # send file from cache folder to user
    return send_file(file_name)

# route for static files. like html and css files.
@app.route('/html/<path:path>')
def send_report(path):
    return send_from_directory('html', path)

# route for downloading add-on.
# g stands for get
@app.route('/g/<addon>')  # type: ignore
def addon_download(addon:str):
    # send cached file from addon folder if it exists
    if addon in listdir('addons'):
        return send_file(f'addons/{addon}')
    else:
        # download file from mozilla, if it is not cached
        addon_link_parts = re.findall(r'([0-9]+)_(.*)', addon)[0]
        addon_link_joines = '/'.join(addon_link_parts) 
        download_link = f'https://addons.mozilla.org/firefox/downloads/file/{addon_link_joines}'

        with get(download_link, stream=True) as r:
            r.raise_for_status()
            with open(f'addons/{addon}', 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192): 
                    f.write(chunk)
        # send cached addon to user
        return send_file(f'addons/{addon}')

# route for add-on page
# a stands for add-on
@app.route('/a/<addon>')  # type: ignore
def addon_page(addon:str):
    addon_page = get(f'https://addons.mozilla.org/en-US/firefox/addon/{addon}').text

    bs = bs4.BeautifulSoup(addon_page, features="html.parser")

    # try getting different page elements from add-on page.
    # try...except structure is used to prevent it from crashing, when
    # some elements do not exist in the page.
    try:
        title = bs.find("h1", {"class": "AddonTitle"}).text
    except AttributeError:
        title = ''
    title = title.split(" by ")

    try:
        summary = bs.find("p", {"class": "Addon-summary"}).text
    except AttributeError:
        summary = ''

    try:
        users = bs.findAll("dd", {"class": "MetadataCard-content"})[0].text
    except AttributeError:
        users = ''

    try:
        reviews = bs.find("a", {"class": "AddonMeta-reviews-content-link"}).text
    except AttributeError:
        reviews = ''

    try:
        stars = bs.find("div", {"class": "AddonMeta-rating-title"}).text
    except AttributeError:
        stars = ''

    try:
        install_link = bs.findAll('a', {'class': "InstallButtonWrapper-download-link"})[0]
    except AttributeError:
        install_link = ''

    try:
        description = bs.find("div", {"class", "AddonDescription-contents"}).text
    except AttributeError:
        description = ''
    
    try:
        icon = bs.find("img", {"class": "Addon-icon-image"})["src"]
        # substitute link for icon image, with /p/ route link.
        # this is done to be able to proxy image for user, instead of directly linking to mozilla.
        icon = re.sub(r'https://addons.mozilla.org/(.+)', r'../p/\1', icon)
    except:
        icon = ''


    # substitute installation link with /g/ route, so thet
    # the add-on is sent from server to the user, instead of giving direct link to mozilla
    # for example, this link:
    # https://addons.mozilla.org/firefox/downloads/file/123/funny-addon.xpi
    # will be substituted into this link:
    # ../g/123_funny-addon.xpi
    install_link = re.sub(r'(https://addons.mozilla.org/firefox/downloads/file)/([0-9]+)/(.*\.xpi)',
    r'../g/\2_\3', install_link['href'])


    more_info = bs.find("dl", {"class": "AddonMoreInfo-dl"})
    release_notes = bs.find("section", {"class": "AddonDescription-version-notes"})
    
    
    # get all screenshot images from page
    screenshots_tags = bs.findAll("img", {"class": "ScreenShots-image"})
    # substitute their link with /p/ link to let the server proxy them instead of,
    # directly linking them to mozilla
    for image in screenshots_tags:
        image['src'] = re.sub(r'https://addons.mozilla.org/(.+)', r'../p/\1', image['src'])

    # start putting extracted and modified elements
    # in page template and send it to user
    template = addon_page_template
    final = template.replace("---title---", f"Mozilfun! - {title[0]}").replace("---ext-name---", title[0]).replace(
        "---developer---", title[1]).replace("---summary---", summary).replace("---dl-botton---", install_link).replace(
        "---description---", description).replace("---screenshots---", "".join(str(item) for item in screenshots_tags)).replace(
        "---icon---", icon).replace("---stars---", stars).replace("---users---", users).replace("---reviews---", reviews).replace(
        "---moreinfo---", str(more_info)).replace("---release-notes---", str(release_notes))
    
    return final


# route for query page
# s stands for search
@app.route('/s/', methods=['GET'])
def give_output():
    # link is like this:
    # /s/?query=funny-query
    # line below, extracts query from link
    query = request.args.get('query')

    # get page from mozilla
    search_page = get(f'https://addons.mozilla.org/en-US/firefox/search/?q={query}').text

    # start exctracting elements from page.
    bs = bs4.BeautifulSoup(search_page, features="html.parser")
    entries = bs.findAll('div', {'class': "SearchResult-contents"})

    output_html = ''

    # substitute links with /a/ route
    # so that they are shown to user from mozilfun.
    for entry in entries:
        link = entry.findAll('a', {'class':'SearchResult-link'})[0]
        link['href'] = re.sub(r'(/en-US/firefox/addon)/([^/]+)/?(.*)',
         r'../a/\2', link['href'])
        output_html += entry.prettify()

    output_final = query_html_template.replace('###', output_html)
    return output_final


# this can be changed in production
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
