# Contributing

## Editing existing content
You can edit the site from your browser, and you don't need to know git.

Let's say you notice a typo and want to fix it. Make a [github.com account](https://github.com/) if you don't have one, then:

1. Click the pencil icon in the top right corner of the page. It'll say you can't edit directly and ask you to fork the repository. Do that.
2. Make your changes in the editor.
3. Click "Commit changes" and write a short message about your change(s). Click the green button "Propose changes" to proceed.
4. You'll be taken to the review page, where you should click "Create pull request" to send it in for moderator review.

# Content overview
Content in files such as `docs/books/ham-on-rye-37.md` is kept between dashes `---` called frontmatter. It looks like this:

```frontmatter
---
book_id: 37
book_title: Ham On Rye
image: null
pub_date: 28/7/1982
publisher: Black Sparrow Press
genre: prose
is_major: 'yes'
notes: Written in San Pedro, CA
---
```

Usually that's the only section you'll want to edit. 

Content below these lines are usually macros, which are used to generate a design and related content. Macros look like this:

{% raw %}
```jinja
{{ section_title() }}
{{ book_info() }}
{{ notes_section() }}
{{ works_section() }}
```
{% endraw %}

Adding something below or in-between these macros will add it to the page. For example, if you'd like to add a link to a forum discussion after the notes section, you'd edit the page and add this:

{% raw %}
```jinja
{{ section_title() }}
{{ book_info() }}
{{ notes_section() }}

## Forum References
- [Discussion (published poem is incomplete)](https://bukowskiforum.com/showthread.php?t=7031)

{{ works_section() }}
```
{% endraw %}

## Adding a new book, manuscript, work, etc.
Pick out a new, unique `internal id` for the new item. Sequential ids are preferred. The easiest way to find one is to sort an [index on the website](books/index.md) by internal id.

After you've chosen an id, go to the [docs folder in the repository](https://github.com/BukowskiForum/bukowskidb/tree/main/docs), select the folder of the content type you want to add, then click "add file". The filename should not contain any spaces nor more than 50 characters, and it should end with a dash and the internal id number, like this: `ham-on-rye-37.md`.

Then paste one of the following templates into the new file, and fill in the fields. 

### Books

{% raw %}
```jinja
---
book_id:
book_title:
image:
pub_date:
publisher:
genre:
is_major:
notes:
works_included:
- work_id:
  book_page: ''
---

{{ section_title() }}
{{ book_info() }}
{{ notes_section() }}
{{ works_section() }}
```
{% endraw %}

### Broadsides

{% raw %}
```jinja
---
broadside_id:
broadside_title:
publisher:
pub_date:
broadside_image:
notes:
works_included:
- work_id:
---

{{ section_title() }}
{{ book_info() }}
{{ section_image() }}
{{ notes_section() }}
{{ works_section() }}
```
{% endraw %}

### Magazines

{% raw %}
```jinja
---
magazine_id:
magazine_title:
pub_date:
volume:
number:
month:
notes:
pub_date1:
pub_date2:
image:
works_included:
- work_id:
  magazine_page: ''
  published_as: ''
---

{{ section_title() }}
{{ magazine_info() }}
{{ section_image() }}
{{ notes_section() }}
{{ works_section() }}
```
{% endraw %}

### Manuscripts

{% raw %}
```jinja
---
magazine_id:
magazine_title:
pub_date:
volume: ''
number:
month: ''
notes:
pub_date1:
pub_date2:
image:
works_included:
- work_id:
  magazine_page: ''
  published_as: ''
- work_id:
  magazine_page: ''
  published_as: ''
---

{{ section_title() }}
{{ magazine_info() }}
{{ section_image() }}
{{ notes_section() }}
{{ works_section() }}
```
{% endraw %}

### Recordings

{% raw %}
```jinja
---
recording_id:
recording_date:
recording_event:
notes:
releases:
- release_id:
  recording_title:
  release_date:
  release_format:
  release_image:
  release_label:
  release_notes:
    1962
  tracks:
  - track_number: 1
    work_id:
    audio_link:
  - track_number: 2
    work_id:
    audio_link:
  - track_number: 3
    work_id:
    audio_link:
  - track_number: 4
    work_id:
    audio_link:
  - track_number: 5
    work_id:
    audio_link:
  - track_number: 6
    work_id:
    audio_link:
  - track_number: 7
    work_id:
    audio_link:
  - track_number: 8
    work_id:
    audio_link:
  - track_number: 9
    work_id:
    audio_link:
---

{{ section_title() }}
{{ recording_info() }}
{{ notes_section() }}
{{ release_info() }}
```
{% endraw %}

### Works

{% raw %}
```jinja
---
work_id:
work_title:
work_written:
written_date:
work_collected:
work_category:
notes:
alternate_versions:
-
---

{{ section_title() }}
{{ work_info() }}
{{ notes_section() }}
{{ appearances_section() }}
{{ alternate_versions_section() }}
```
{% endraw %}

After you fill in the fields, commit the changes and create a pull request for moderator review.

### Letters

Letters we store as simple images, no other file is needed. Add the letter to the `docs/manuscripts` folder. The filename should follow the format `letterYYYY-MM-DD-correspondent.jpg`, nothing else required.

## Technical details
- In general, `main.py` holds the logic, design and markup of the site.
- The markdown files, such as `docs/books/ham-on-rye-37.md`, contain the content. 
    (There are exceptions, and there's a bit of templating in `overrides/main.html` but for the most part that's how it works.)
- You can run the site locally by following instructions at [mkdocs material](https://squidfunk.github.io/mkdocs-material/getting-started/).
- I'm happy to accept pull requests for big things such as design and structure changes. Let's talk about it on the forum before you put in the work.