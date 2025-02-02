from flask import Flask, send_from_directory, send_file, request
from requests import get
import bs4
import re
from os import listdir, makedirs

app = Flask(__name__)

homepage_html = open('html/home.html').read()
query_html_template = open('html/query.html').read()
addon_page_template = open('html/addon.html').read()
makedirs('addons', exist_ok=True)
makedirs('cache', exist_ok=True)

@app.route('/')
def get_home():
    return homepage_html

@app.route('/p/<path:path>')
def proxy_data(path):
    download_link = 'https://addons.mozilla.org/' + path
    file_name = 'cache/' + download_link.replace('/', '_')
    with get(download_link, stream=True) as r:
        r.raise_for_status()
        with open(file_name, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192): 
                f.write(chunk)
    return send_file(file_name)

@app.route('/html/<path:path>')
def send_report(path):
    return send_from_directory('html', path)

@app.route('/g/<addon>')  # type: ignore
def addon_download(addon:str):
    if addon in listdir('addons'):
        return send_file(f'addons/{addon}')
    else:
        addon_link_parts = re.findall(r'([0-9]+)_(.*)', addon)[0]
        addon_link_joines = '/'.join(addon_link_parts) 
        download_link = f'https://addons.mozilla.org/firefox/downloads/file/{addon_link_joines}'

        with get(download_link, stream=True) as r:
            r.raise_for_status()
            with open(f'addons/{addon}', 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192): 
                    f.write(chunk)
        return send_file(f'addons/{addon}')

@app.route('/a/<addon>')  # type: ignore
def addon_page(addon:str):
    addon_page = get(f'https://addons.mozilla.org/en-US/firefox/addon/{addon}').text
    #addon_page = open("test1.html").read()
    bs = bs4.BeautifulSoup(addon_page, features="html.parser")

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

    install_link = re.sub(r'(https://addons.mozilla.org/firefox/downloads/file)/([0-9]+)/(.*\.xpi)',
    r'../g/\2_\3', install_link['href'])

    
    more_info = bs.find("dl", {"class": "AddonMoreInfo-dl"})
    release_notes = bs.find("section", {"class": "AddonDescription-version-notes"})
    screenshots_tags = bs.findAll("img", {"class": "ScreenShots-image"})
    screenshots_slider = []
    for image in screenshots_tags:
        image['src'] = re.sub(r'https://addons.mozilla.org/(.+)', r'../p/\1', image['src'])
        screenshots_slider.append(f'<div class="mySlides fade"><img src="{image["src"]}" style="width:100%;"></div>')
    ### Bug: Images are not shown completely.
    try:
        icon = bs.find("img", {"class": "Addon-icon-image"})["src"]
        icon = re.sub(r'https://addons.mozilla.org/(.+)', r'../p/\1', icon)

    except:
        icon = ''

    try:
        description = str(bs.find("section", {"class", "AddonDescription"}))
    except AttributeError:
        description = ''
    
    if bs.find("a", {"class":"PromotedBadge-link--recommended"}) != None:
        recommended = True
    else: recommended = False
    recommendedHTML = '''<section class="Card-contents" style="text-align: center; font-family: Danila; font-size: x-large; color: yellow"> 
        Recommended by firefox :)</section>'''


    template = addon_page_template
    final = template.replace("---title---", f"Mozilfun! - {title[0]}").replace("---ext-name---", title[0]).replace(
        "---developer---", title[1]).replace("---summary---", summary).replace("---dl-botton---", install_link).replace(
        "---description---", description).replace("---screenshots---", "".join(screenshots_slider)).replace("---icon---", icon).replace(
        "---stars---", stars).replace("---users---", users).replace("---reviews---", reviews).replace("---moreinfo---", str(more_info)).replace(
        "---release-notes---", str(release_notes) if release_notes != None else "").replace("---recommended---", 
        recommendedHTML if recommended else "").replace('<section class="Card ShowMoreCard AddonDescription-version-notes ShowMoreCard--expanded Card--no-footer">',
        '<section class="Card ShowMoreCard AddonDescription-version-notes ShowMoreCard--expanded Card--no-footer" style="margin-bottom: 10px;">')
    
    return final.replace("None", "")


@app.route('/s/', methods=['GET'])
def give_output():
    query = request.args.get('query')
    search_page = get(f'https://addons.mozilla.org/en-US/firefox/search/?q={query}').text

    bs = bs4.BeautifulSoup(search_page, features="html.parser")
    entries = bs.findAll('div', {'class': "SearchResult-contents"})

    output_html = ''

    for entry in entries:
        link = entry.findAll('a', {'class':'SearchResult-link'})[0]
        link['href'] = re.sub(r'(/en-US/firefox/addon)/([^/]+)/?(.*)',
         r'../a/\2', link['href'])
        # link.string.replace_with('get addon')
        output_html += entry.prettify()
        # output_html += link.prettify()

    output_final = query_html_template.replace('###', output_html)
    return output_final


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
