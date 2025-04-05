import os
import datetime
import re
import yaml
import html  # Added for HTML escaping

# This script is used to generate markdown docs for the "Bukowski Database" 
# It reads each file's frontmatter and spits out some formatted content. 
# It's one big file because mkdocs-macros works better with one file.

# Global cache for frontmatter
_METADATA_CACHE = {}
# Directory listing cache
_DIR_CACHE = {}
# Cache for work IDs to filenames
_WORK_ID_CACHE = {}
# Cache for checking manuscript altered
_MANUSCRIPT_CACHE = {}
# Cache for manuscripts containing a specific work
_MANUSCRIPT_WORK_MAP = {}

### Macros for embedding in markdown docs ###

# Universal "title" macro
def define_env(env):
    # Initialize cache at the start of environment setup
    global _METADATA_CACHE
    if not _METADATA_CACHE:
        _METADATA_CACHE = {}
    
    @env.macro
    def section_title():
        # Prioritize handling works if a specific work title is provided.
        if "work_title" in env.page.meta:
            title = env.page.meta["work_title"]
            work_written = env.page.meta.get("work_written", "")
            written_date = env.page.meta.get("written_date", "")
            date_str = ""
            if work_written:
                if written_date == "approximate":
                    date_str = f"(circa {work_written})"
                else:
                    date_str = f"({work_written})"
            return f"# {title} {date_str}".strip()

        # Use the centralized content type detection for all other types.
        content_type = detect_content_type(env.page.meta)

        if content_type == "Magazine":
            title = env.page.meta.get("magazine_title", "Untitled Magazine")
            month = env.page.meta.get("month", "")
            year = env.page.meta.get("pub_date", "").strip("'")
            volume = env.page.meta.get("volume", "")
            number = env.page.meta.get("number", "")
            
            # Format date and volume/number information
            date_part = f"({month} {year})" if month else f"({year})" if year else ""
            vol_num = []
            if volume:
                vol_num.append(f"vol. {volume}")
            if number:
                vol_num.append(f"no. {number}")
            vol_num_str = ", ".join(vol_num)
            return f"# *{title}* {date_part}{', ' + vol_num_str if vol_num_str else ''}".strip()

        elif content_type == "Broadside":
            title = env.page.meta.get("broadside_title", "Untitled Broadside")
            pub_date = env.page.meta.get("pub_date", "").strip("'")
            year = pub_date if pub_date else "[Year Unknown]"
            return f"# Broadside: _{title}_ ({year})"

        elif content_type == "Manuscript":
            title = env.page.meta.get("manuscript_title", "Untitled Manuscript")
            circa = env.page.meta.get("circa", "")
            dated = env.page.meta.get("dated", "")
            date_parts = []
            if circa:
                date_parts.append(f"circa {circa}")
            else:
                # Expecting format like 0/4/1991, split into month/day/year.
                parts = re.split(r'[/-]', dated)
                if len(parts) >= 3:
                    month_part = parts[1].lstrip('0')  # Remove leading zero, if any.
                    year_part = parts[2]
                    if month_part:
                        try:
                            month_name = datetime.date(1900, int(month_part), 1).strftime('%B')
                            date_parts.append(f"{month_name} {year_part}")
                        except ValueError:
                            date_parts.append(year_part)
                elif dated:
                    date_parts.append(dated)
            date_str = f"({', '.join(date_parts)})" if date_parts else ""
            return f"# Manuscript: _{title}_ {date_str}".strip()

        elif content_type == "Recording":
            event = env.page.meta.get("recording_event", "Recording")
            rec_date = env.page.meta.get("recording_date", "").strip("'")
            year = rec_date.split('/')[-1] if rec_date else ""
            return f"# {event} ({year})" if year else f"# {event}"

        elif content_type == "Book":
            title = env.page.meta.get("book_title", "Untitled Book")
            pub_date = env.page.meta.get("pub_date", "")
            year = pub_date.split("/")[-1] if pub_date else ""
            return f"# _{title}_ ({year})"

        else:  # Fallback for other content types.
            title = env.page.meta.get("title", "Untitled Work")
            pub_date = env.page.meta.get("pub_date", "")
            year = pub_date.split("/")[-1] if "/" in pub_date else pub_date
            year_part = f"({year})" if year else ""
            return f"# _{title}_ {year_part}".strip()

    # used by books and broadsides
    @env.macro
    def book_info():
        # Get publisher and publication date from frontmatter
        publisher = env.page.meta.get("publisher", "Unknown Publisher")
        pub_date = env.page.meta.get("pub_date", "")
        is_major = env.page.meta.get("is_major", "no") == "yes"
        genre = env.page.meta.get("genre", "")

        major_badge = (
            " <span style='color: var(--md-accent-fg-color)'>"
            ":material-typewriter:{title='This is a major work'}</span>"
            if is_major
            else ""
        )
        
        # Format genre info for the sentence
        genre_text = ""
        if genre == "both":
            genre_text = "a collection of poetry and prose "
        elif genre == "poetry":
            genre_text = "a poetry collection "
        elif genre == "prose":
            genre_text = "a prose collection "
        # Handle "neither" the same as empty
        
        # Use original format if no genre or "neither"
        if genre_text:
            return f"Published as {genre_text}by **_{publisher}_**, {pub_date}{major_badge}"
        else:
            return f"Published by **_{publisher}_**, {pub_date}{major_badge}"

    # used by all types EXCEPT works. 
    @env.macro
    def works_section():
        works_included = env.page.meta.get("works_included", [])
        if not works_included:
            return ""
        
        content_type = detect_content_type(env.page.meta)
        
        # Get the docs directory and works path
        docs_dir = env.conf.get("docs_dir", "docs")
        paths = get_content_paths(docs_dir)
        works_dir = paths["works"]
        
        try:
            work_files = os.listdir(works_dir)
        except Exception:
            return "Error: Cannot access works directory."

        lines = []
        lines.append(f"## Works in this {content_type} {{ data-search-exclude }}")
        
        for work in works_included:
            work_id = str(work.get("work_id", ""))
            
            # Get content-type specific fields
            page_info = ""
            if content_type == "Magazine":
                if work.get("magazine_page"):
                    page_info = f" - pg. {work.get('magazine_page')}"
            elif content_type in ["Book", "Broadside"]:
                if work.get("book_page"):
                    page_info = f" - pg. {work.get('book_page')}"
                    
            published_as = f" as '{work.get('published_as', '')}'" if work.get('published_as') else ""

            # Add badges/icons
            badges = []
            if content_type == "Manuscript" and work.get('altered', 'no') == 'yes':
                badges.append("<span style='color: var(--md-accent-fg-color)'>"
                             ":material-lead-pencil:{title='Manuscript differs from collected version'}</span>")
                
            # Use find_work_by_id instead of manually searching
            match_file, metadata = find_work_by_id(works_dir, work_id)
            
            if not match_file:
                lines.append(f"- Work with ID {work_id}{page_info}{published_as}")
                continue

            # Get work metadata
            relative_link = f"../works/{match_file}"
            
            # Get work title
            work_title = get_work_title(metadata, match_file)
            
            # Get date information
            work_written = metadata.get("work_written", "")
            date_is_approximate = metadata.get("written_date") == "approximate"
            date_part = ""
            if work_written:
                date_prefix = "circa " if date_is_approximate else ""
                date_part = f" - {date_prefix}{work_written}"
            
            # Build the line with proper badge placement
            badges_str = " " + " ".join(badges) if badges else ""
            lines.append(f"- [{work_title}]({relative_link}){badges_str}{page_info}{published_as}{date_part}")
            
        return "\n".join(lines)

    @env.macro
    def notes_section():
        """
        Creates a Material note admonition if notes exist in frontmatter.
        """
        notes = env.page.meta.get("notes", "")
        if notes:
            return f'!!! note \n\n    {notes}'
        return ""

    @env.macro
    def section_image():
        if img := env.page.meta.get("broadside_image"):
            return f'![Broadside Image]({img})'
        
        if img := env.page.meta.get("image"):
            return f'![Image]({img})'
        
        return ""  # No image found

    # Magazine-specific macros
    @env.macro
    def magazine_info():
        # Get magazine publication information
        volume = env.page.meta.get("volume", "")
        number = env.page.meta.get("number", "")
        month = env.page.meta.get("month", "")
        pub_date1 = env.page.meta.get("pub_date1", "")
        pub_date2 = env.page.meta.get("pub_date2", "")
        
        parts = []
        
        # Add volume/number info if available
        if volume:
            parts.append(f"Volume {volume}")
        if number:
            parts.append(f"Number {number}")
            
        # Format date information
        date_info = []
        if month:
            date_info.append(month)
            
        # Handle publication dates
        if pub_date1 and pub_date2:
            date_info.append(f"Published {pub_date1} - {pub_date2}")
        elif pub_date1:
            date_info.append(f"Published {pub_date1}")
            
        # Combine all parts
        if parts and date_info:
            return f"**{', '.join(parts)}** | {', '.join(date_info)}"
        elif parts:
            return f"**{', '.join(parts)}**"
        elif date_info:
            return f"{', '.join(date_info)}"
        else:
            return "Publication details not available"

    # Manuscript-specific macros
    @env.macro
    def manuscript_info():
        # Get manuscript metadata from frontmatter
        circa = env.page.meta.get("circa", "").strip()
        dated = env.page.meta.get("dated", "").strip()
        method = env.page.meta.get("method", "").strip()
        m_type = env.page.meta.get("manuscript_type", "").strip()

        # Use raw 'dated' field if available; otherwise use 'circa'
        if dated:
            date_str = dated
        elif circa:
            date_str = circa
        else:
            date_str = ""
            
        parts = []
        # Bold the date portion
        if date_str:
            parts.append(f"**{date_str}**")
        # Italicize the manuscript type
        if m_type:
            parts.append(f"*{m_type.lower()}*")
        # Method will be plain lowercase text
        if method:
            parts.append(method.lower())

        return ", ".join(parts) + "\n"

    # Recording-specific macros
    @env.macro
    def recording_info():
        """Formats the recording date in bold"""
        date = env.page.meta.get("recording_date", "")
        return f"Recording Date: **{date}**" if date else ""

    @env.macro
    def release_info():
        """Generates release sections with track listings"""
        releases = env.page.meta.get("releases", [])
        if not releases:
            return ""
        
        docs_dir = env.conf.get("docs_dir", "docs")
        paths = get_content_paths(docs_dir)
        works_dir = paths["works"]
        work_files = os.listdir(works_dir) if os.path.exists(works_dir) else []
        
        lines = ["## Releases"]
        
        for release in releases:
            # Release header
            title = release.get("recording_title", "Untitled Release")
            fmt = release.get("release_format", "")
            label = release.get("release_label", "")
            date = release.get("release_date", "")
            
            header_parts = [f"### {title}"]
            if fmt: header_parts.append(f"({fmt})")
            if label: header_parts.append(f"- {label}")
            if date: header_parts.append(f"- {date}")
            
            lines.append(" ".join(header_parts))

            # Release notes
            if notes := release.get("release_notes"):
                lines.append(f'!!! note \n\n    {notes}\n')

            # Release image
            if img := release.get("release_image"):
                lines.append(f"![{title} cover]({img})\n")

            # Track listing - sort by track number
            tracks = release.get("tracks", [])
            # Sort tracks by track number (convert to int for proper numeric sorting)
            sorted_tracks = sorted(tracks, key=lambda x: int(x.get("track_number", 0)))
            
            lines.append("**Track Listing:**\n")
            for track in sorted_tracks:
                work_id = str(track.get("work_id", ""))
                track_num = track.get("track_number", "")
                
                # Find work metadata
                match_file, metadata = find_work_by_id(works_dir, work_id)
                if match_file:
                    work_title = get_work_title(metadata, match_file)
                    # Add hyphen for proper list item formatting
                    line = f"- [{work_title}](../works/{match_file}) - _track {track_num}_"
                else:
                    line = f"- Work ID {work_id} - _track {track_num}_"
                
                lines.append(line)
            
            lines.append("")  # Add spacing between releases
            
        return "\n".join(lines)

    # Works-specific macros
    @env.macro
    def work_info():
        """Displays work metadata with collection status icon"""
        category = env.page.meta.get("work_category", "Uncategorized Work")
        written = env.page.meta.get("work_written", "")
        written_date = env.page.meta.get("written_date", "")
        collected = env.page.meta.get("work_collected", "no") == "yes"

        # Format date information
        date_str = ""
        if written:
            if written_date == "approximate":
                date_str = f"(circa {written})"
            else:
                date_str = f"({written})"
        
        # Create collected work badge
        collected_badge = (
            " <span style='color: var(--md-accent-fg-color)'>"
            ":material-book:{title='Collected work'}</span>"
            if collected
            else ""
        )
        
        return f"**{category}** {date_str}{collected_badge}".strip()
    
    @env.macro
    def appearances_section():
        # Get the current work's ID
        current_work_id = str(env.page.meta.get("work_id", ""))
        if not current_work_id:
            return ""  # No work ID to look for

        # Define your docs directory and individual content type paths
        docs_dir = env.conf.get("docs_dir", "docs")
        paths = get_content_paths(docs_dir)
        directories = {
            "Books": paths["books"],
            "Magazines": paths["magazines"],
            "Broadsides": paths["broadsides"],
            "Manuscripts": paths["manuscripts"],
            "Recordings": paths["recordings"]
        }

        # Map each content type to its corresponding extractor
        extractors = {
            "Books": works_included_extractor,
            "Magazines": works_included_extractor,
            "Broadsides": works_included_extractor,
            "Manuscripts": works_included_extractor,
            "Recordings": recording_extractor
        }

        # Define custom section titles for the output
        section_titles = {
            "Books": "Appears in Books",
            "Magazines": "Appears in Magazines",
            "Broadsides": "Appears in Broadsides",
            "Manuscripts": "Appears in Manuscripts",
            "Recordings": "Recorded Readings"
        }

        # Scan each directory using the unified scanning helper
        result = []
        for content_type, directory in directories.items():
            if content_type == "Manuscripts":
                items = get_manuscripts_for_work(current_work_id, docs_dir)
            else:
                items = scan_docs(directory, current_work_id, content_type, extractors[content_type])
            if not items:
                continue
            result.append(f"## {section_titles[content_type]}")
            for item in items:
                # Format a basic link; further formatting can be done per type if needed.
                link = f"[{item['title']}](../{item['directory']}/{item['filename']})"
                line = f"- {link}"
                # Optionally append extra info for different content types
                if content_type == "Magazines":
                    # Start building the magazine info
                    magazine_info = []
                    
                    # Add volume/number information if available
                    vol_num_parts = []
                    if "volume" in item and item["volume"]:
                        vol_num_parts.append(f"vol. {item['volume']}")
                    if "number" in item and item["number"]:
                        vol_num_parts.append(f"no. {item['number']}")
                    
                    if vol_num_parts:
                        magazine_info.append(", ".join(vol_num_parts))
                    
                    # Add date information
                    date_parts = []
                    if "month" in item and item["month"]:
                        date_parts.append(item["month"])
                    if "year" in item and item["year"]:
                        date_parts.append(item["year"])
                    
                    if date_parts:
                        magazine_info.append(" ".join(date_parts))
                    
                    # Add page number if available
                    if "page" in item:
                        magazine_info.append(f"pg. {item['page']}")
                    
                    # Add all the info to the line
                    if magazine_info:
                        line += f" - {', '.join(magazine_info)}"
                
                elif content_type == "Books":
                    # Build book information
                    book_info = []
                    
                    # Add year if available
                    if "year" in item and item["year"]:
                        book_info.append(item["year"])
                    
                    # Add page number if available
                    if "page" in item:
                        book_info.append(f"pg. {item['page']}")
                    
                    # Add all the info to the line
                    if book_info:
                        line += f" - {', '.join(book_info)}"
                
                elif content_type == "Broadsides":
                    # Broadside information
                    broadside_info = []
                    
                    # Add publication year if available
                    if "year" in item and item["year"]:
                        broadside_info.append(item["year"])
                    
                    # Broadside publications might not have page numbers, but include if available
                    if "page" in item:
                        broadside_info.append(f"pg. {item['page']}")
                    
                    # Add all the info to the line
                    if broadside_info:
                        line += f" - {', '.join(broadside_info)}"
                elif content_type == "Manuscripts":
                    # Manuscript information
                    manuscript_info = []
                    
                    # Add date information if available
                    if "date" in item and item["date"]:
                        manuscript_info.append(item["date"])
                    
                    # Add method information if available
                    if "method" in item and item["method"]:
                        manuscript_info.append(item["method"].lower())
                    
                    # Add icons/badges for manuscripts
                    if "altered" in item and item["altered"]:
                        line += " <span style='color: var(--md-accent-fg-color)'>" \
                               ":material-lead-pencil:{title='Manuscript differs from collected version'}</span>"
                    
                    # Add all the info to the line
                    if manuscript_info:
                        line += f" - {', '.join(manuscript_info)}"
                result.append(line)
            result.append("")  # Add spacing between sections
        return "\n".join(result)

    @env.macro
    def alternate_versions_section():
        alts = env.page.meta.get("alternate_versions", [])
        if not alts:
            return ""
        
        docs_dir = env.conf.get("docs_dir", "docs")
        paths = get_content_paths(docs_dir)
        works_dir = paths["works"]
        
        lines = ["## Alternate Versions"]
        for alt in alts:
            work_id = str(alt)
            match_file, metadata = find_work_by_id(works_dir, work_id)
            if match_file:
                title = get_work_title(metadata, match_file)
                relative_link = f"../works/{match_file}"
                lines.append(f"- [{title}]({relative_link})")
            else:
                lines.append(f"- Work with ID {work_id}")
        
        return "\n".join(lines)

    @env.macro
    def generate_index(section="books"):
        """
        Aggregates metadata for a given section and returns a Markdown-formatted table.
        Handles special characters in titles by escaping them for Markdown links.
        """
        docs_dir = env.conf.get("docs_dir", "docs")
        paths = get_content_paths(docs_dir)
        section_dir = paths.get(section, None)
        if not section_dir or not os.path.exists(section_dir):
            return f"**Error:** Section '{section}' directory not found."
        
        rows = []
        # Define table headers according to section type
        if section.lower() == "books":
            headers = ["Title", "Publication Date", "Publisher", "Genre", "Internal ID", "Major"]
        elif section.lower() == "magazines":
            headers = ["Title", "Publication Date", "Month", "Volume", "Number", "Internal ID"]
        elif section.lower() == "broadsides":
            headers = ["Title", "Publication Date", "Publisher", "Internal ID"]
        elif section.lower() == "manuscripts":
            headers = ["Title", "Date", "Type", "Internal ID"]
        elif section.lower() == "recordings":
            headers = ["Title", "Recording Date", "Releases", "Internal ID"]
        elif section.lower() == "works":
            headers = ["Title", "Work Written", "Category", "Internal ID", "Collected", "Manuscript"]
        else:
            headers = ["Title", "Publication Date", "Publisher", "Internal ID"]
        
        # Build the header row and divider row for the Markdown table.
        header_row = "| " + " | ".join(headers) + " |"
        divider_row = "| " + " | ".join(["---"] * len(headers)) + " |"
        rows.append(header_row)
        rows.append(divider_row)
        
        # List and sort the markdown files in the target directory for consistency.
        try:
            files = sorted(os.listdir(section_dir))
        except Exception as e:
            return f"**Error:** Unable to list files in '{section_dir}': {e}"
        
        for filename in files:
            # Skip index.md to avoid self-reference
            if filename == "index.md":
                continue
            
            if filename.endswith(".md"):
                filepath = os.path.join(section_dir, filename)
                metadata = read_work_metadata(filepath)
                # Keep the .md extension for MkDocs initial link resolution
                relative_link = filename 
                
                # Updated function to always use Markdown links and escape problematic characters
                def create_safe_link(title, link):
                    # Escape '[' and ']' within the link text part to avoid breaking Markdown syntax
                    # Parentheses generally don't need escaping within the link text.
                    escaped_title = title.replace('[', '\\[').replace(']', '\\]')
                    # Always return a standard Markdown link
                    return f"[{escaped_title}]({link})"
                
                if section.lower() == "books":
                    book_id = str(metadata.get("book_id", "")).strip()
                    # Use the original title for display, but escape it for the link
                    title = str(metadata.get("book_title", "")).strip() or os.path.splitext(filename)[0]
                    title_link = create_safe_link(title, relative_link) # Use the updated function
                    pub_date = str(metadata.get("pub_date", "")).strip()
                    publisher = str(metadata.get("publisher", "")).strip()
                    genre = str(metadata.get("genre", "")).strip()
                    # Updated code snippet for "Major":
                    is_major_raw = str(metadata.get("is_major", "no")).strip().lower()
                    if is_major_raw == "yes":
                        major = (
                            "<span style='display:none' data-sort='1'>1</span>"
                            "<span>:material-typewriter:{title='This is a major work'}</span>"
                        )
                    else:
                        major = "<span style='display:none' data-sort='0'>0</span>"
                    # Reordered the values to match the new header order
                    row = f"| {title_link} | {pub_date} | {publisher} | {genre} | {book_id} | {major} |"
                elif section.lower() == "magazines":
                    mag_id = str(metadata.get("magazine_id") or "").strip()
                    # Use the original title for display, but escape it for the link
                    title = (str(metadata.get("magazine_title") or "").strip() or os.path.splitext(filename)[0])
                    title_link = create_safe_link(title, relative_link) # Use the updated function
                    # Use pub_date1 if available, otherwise use pub_date
                    pub_date = str(metadata.get("pub_date1") or metadata.get("pub_date") or "").strip()
                    month = str(metadata.get("month") or "").strip()
                    volume = str(metadata.get("volume") or "").strip()
                    number = str(metadata.get("number") or "").strip()
                    row = f"| {title_link} | {pub_date} | {month} | {volume} | {number} | {mag_id} |"
                elif section.lower() == "broadsides":
                    broad_id = str(metadata.get("broadside_id", "")).strip()
                    # Use the original title for display, but escape it for the link
                    title = str(metadata.get("broadside_title", "")).strip() or os.path.splitext(filename)[0]
                    title_link = create_safe_link(title, relative_link) # Use the updated function
                    pub_date = str(metadata.get("pub_date", "")).strip()
                    publisher = str(metadata.get("publisher", "")).strip()
                    row = f"| {title_link} | {pub_date} | {publisher} | {broad_id} |"
                elif section.lower() == "manuscripts":
                    ms_id = str(metadata.get("manuscript_id", "")).strip()
                    # Use the original title for display, but escape it for the link
                    title = str(metadata.get("manuscript_title", "")).strip() or os.path.splitext(filename)[0]
                    title_link = create_safe_link(title, relative_link) # Use the updated function
                    date_field = str(metadata.get("dated", "") or metadata.get("circa", "")).strip()
                    ms_type = str(metadata.get("manuscript_type", "")).strip()
                    row = f"| {title_link} | {date_field} | {ms_type} | {ms_id} |"
                elif section.lower() == "recordings":
                    rec_id = str(metadata.get("recording_id", "")).strip()
                    # Use the original title for display, but escape it for the link
                    title = str(metadata.get("recording_event", "")).strip() or os.path.splitext(filename)[0]
                    title_link = create_safe_link(title, relative_link) # Use the updated function
                    rec_date = str(metadata.get("recording_date", "")).strip()
                    releases = metadata.get("releases", [])
                    releases_count = str(len(releases)) if releases else "0"
                    row = f"| {title_link} | {rec_date} | {releases_count} | {rec_id} |"
                elif section.lower() == "works":
                    work_id = str(metadata.get("work_id", "") if metadata.get("work_id") is not None else "").strip()
                    # Use the original title for display, but escape it for the link
                    title = str(metadata.get("work_title", "")).strip() or os.path.splitext(filename)[0]
                    title_link = create_safe_link(title, relative_link) # Use the updated function
                    work_written = str(metadata.get("work_written", "") if metadata.get("work_written") is not None else "").strip()
                    
                    # Updated collected field with hidden sort value:
                    collected_raw = metadata.get("work_collected", "no")
                    if str(collected_raw).strip().lower() == "yes":
                        collected = (
                            "<span style='display:none' data-sort='1'>1</span>"
                            "<span>:material-book:{title='Collected work'}</span>"
                        )
                    else:
                        collected = "<span style='display:none' data-sort='0'>0</span>"
                    
                    category = str(metadata.get("work_category", "") if metadata.get("work_category") is not None else "").strip()
                    manuscript_icon = check_manuscript_altered(work_id, docs_dir)
                    if manuscript_icon:
                        manuscript = (
                            "<span style='display:none' data-sort='1'>1</span>"
                            "<span>" + manuscript_icon + "</span>"
                        )
                    else:
                        manuscript = "<span style='display:none' data-sort='0'>0</span>"
                    row = f"| {title_link} | {work_written} | {category} | {work_id} | {collected} | {manuscript} |"
                else:
                    identifier = str(metadata.get("id", "")).strip()
                    # Use the original title for display, but escape it for the link
                    title = str(metadata.get("title", "")).strip() or os.path.splitext(filename)[0]
                    title_link = create_safe_link(title, relative_link) # Use the updated function
                    pub_date = str(metadata.get("pub_date", "")).strip()
                    publisher = str(metadata.get("publisher", "")).strip()
                    row = f"| {title_link} | {pub_date} | {publisher} | {identifier} |"
                rows.append(row)
        
        return "\n".join(rows)

############################# Utility functions #############################


def read_work_metadata(filepath):
    """
    Reads the YAML frontmatter from a Markdown file.
    Uses an in-memory cache to avoid repeated disk reads.
    """
    # Check if we already have this file's metadata in cache
    global _METADATA_CACHE
    if filepath in _METADATA_CACHE:
        return _METADATA_CACHE[filepath]
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            contents = f.read()
        if contents.startswith('---'):
            parts = contents.split('---', 2)
            if len(parts) >= 3:
                data = yaml.safe_load(parts[1])
                metadata = data if isinstance(data, dict) else {}
                # Cache the result before returning
                _METADATA_CACHE[filepath] = metadata
                return metadata
    except Exception:
        # Cache empty metadata for failed reads to avoid retrying
        _METADATA_CACHE[filepath] = {}
        return {}
    
    # Cache empty metadata for files without proper frontmatter
    _METADATA_CACHE[filepath] = {}
    return {}

def scan_docs(directory, current_work_id, content_type, extractor):
    """
    Scans the given directory for markdown files that match the criteria.
    Uses caching to improve performance.
    """
    results = []
    if not os.path.exists(directory):
        return results
    
    # Use cached directory listing if available
    global _DIR_CACHE
    if directory not in _DIR_CACHE:
        try:
            _DIR_CACHE[directory] = [f for f in os.listdir(directory) 
                                   if f.endswith(".md")]
        except Exception as e:
            print(f"Error listing directory {directory}: {e}")
            return results
    
    for filename in _DIR_CACHE[directory]:
        filepath = os.path.join(directory, filename)
        metadata = read_work_metadata(filepath)
        item = extractor(metadata, current_work_id, filename, os.path.basename(directory))
        if item:
            results.append(item)
    
    return results

def recording_extractor(metadata, current_work_id, filename, directory_name):
    """
    Extractor for Recordings content type.
    Looks inside "releases" -> "tracks" for a matching work ID.
    """
    releases = metadata.get("releases", [])
    found = False
    for rel in releases:
        for track in rel.get("tracks", []):
            if str(track.get("work_id", "")) == current_work_id:
                found = True
                break
        if found:
            break
    if found:
        info = {
            "title": metadata.get("recording_event", os.path.splitext(filename)[0]),
            "filename": filename,
            "directory": directory_name,
        }
        recording_date = metadata.get("recording_date", "")
        if recording_date and "/" in recording_date:
            parts = recording_date.split("/")
            info["year"] = parts[2] if len(parts) >= 3 else recording_date
        else:
            info["year"] = recording_date
        return info
    return None

def works_included_extractor(metadata, current_work_id, filename, directory_name):
    """
    Extractor for Books, Magazines, Broadsides, and Manuscripts content types.
    Checks the 'works_included' field for a matching work_id.
    """
    works_included = metadata.get("works_included", [])
    for work in works_included:
        if str(work.get("work_id", "")) == current_work_id:
            info = {
                "filename": filename,
                "directory": directory_name,
            }
            # Customize based on available metadata:
            if "book_title" in metadata:
                info["title"] = metadata.get("book_title", os.path.splitext(filename)[0])
                pub_date = metadata.get("pub_date", "")
                info["year"] = pub_date.split("/")[-1] if "/" in pub_date else pub_date
                if work.get("book_page"):
                    info["page"] = work.get("book_page")
            elif "magazine_title" in metadata:
                info["title"] = metadata.get("magazine_title", os.path.splitext(filename)[0])
                info["volume"] = metadata.get("volume", "")
                info["number"] = metadata.get("number", "")
                info["month"] = metadata.get("month", "")
                info["year"] = metadata.get("pub_date", "")
                if work.get("magazine_page"):
                    info["page"] = work.get("magazine_page")
            elif "broadside_title" in metadata:
                info["title"] = metadata.get("broadside_title", os.path.splitext(filename)[0])
            elif "manuscript_title" in metadata:
                info["title"] = metadata.get("manuscript_title", os.path.splitext(filename)[0])
                dated = metadata.get("dated", "")
                if dated and "/" in dated:
                    parts = dated.split("/")
                    info["date"] = f"{parts[0]}/{parts[1]}/{parts[2]}" if len(parts) >= 3 else dated
                else:
                    info["date"] = dated
                    
                # Add manuscript_type and method
                if m_type := metadata.get("manuscript_type", ""):
                    info["manuscript_type"] = m_type
                if method := metadata.get("method", ""):
                    info["method"] = method
                    
                if work.get("altered", "no") == "yes":
                    info["altered"] = True
            return info
    return None

def find_work_by_id(works_dir, work_id):
    """
    Finds a work file by its ID and returns the file path and metadata.
    Uses caching for improved performance.
    """
    # Check if we have a cache for this works directory
    global _WORK_ID_CACHE, _METADATA_CACHE
    
    works_dir_key = works_dir
    if works_dir_key not in _WORK_ID_CACHE:
        _WORK_ID_CACHE[works_dir_key] = {}
        
        try:
            work_files = os.listdir(works_dir)
            # Build ID to filename mapping cache
            for f in work_files:
                if f.endswith(".md"):
                    # Extract the ID from the filename (assuming format: name-ID.md)
                    file_id = f.rsplit("-", 1)[-1].replace(".md", "")
                    _WORK_ID_CACHE[works_dir_key][file_id] = f
        except Exception as e:
            print(f"Error building work ID cache for {works_dir}: {e}")
            return None, None
    
    # Look up the work ID in our cache
    if work_id in _WORK_ID_CACHE[works_dir_key]:
        match_file = _WORK_ID_CACHE[works_dir_key][work_id]
        work_filepath = os.path.join(works_dir, match_file)
        metadata = read_work_metadata(work_filepath)
        return match_file, metadata
    
    return None, None

def get_work_title(metadata, filename):
    """
    Extracts a title from work metadata with a consistent fallback pattern.
    
    Args:
        metadata (dict): The work's metadata
        filename (str): The filename to use as fallback
        
    Returns:
        str: The formatted work title
    """
    return (metadata.get("work_title") or 
            metadata.get("title") or 
            filename.rsplit("-", 1)[0].replace("-", " ").title())

def get_content_paths(docs_dir):
    """
    Returns standardized content paths dictionary based on docs directory
    
    Args:
        docs_dir (str): Base documentation directory
        
    Returns:
        dict: Dictionary of content type paths
    """
    return {
        "works": os.path.join(docs_dir, "works"),
        "books": os.path.join(docs_dir, "books"),
        "magazines": os.path.join(docs_dir, "magazines"),
        "broadsides": os.path.join(docs_dir, "broadsides"),
        "manuscripts": os.path.join(docs_dir, "manuscripts"),
        "recordings": os.path.join(docs_dir, "recordings")
    }

def detect_content_type(metadata):
    """
    Determines content type from metadata
    
    Args:
        metadata (dict): The content's metadata
        
    Returns:
        str: Content type label
    """
    if "magazine_title" in metadata:
        return "Magazine"
    elif "broadside_title" in metadata:
        return "Broadside"
    elif "manuscript_title" in metadata:
        return "Manuscript"
    elif "book_title" in metadata:
        return "Book"
    elif "recording_event" in metadata:
        return "Recording"
    else:
        return "Publication"

def get_manuscripts_for_work(work_id, docs_dir):
    """Get manuscripts containing a specific work and caches the results"""
    global _MANUSCRIPT_WORK_MAP
    
    # If we already have results for this work_id, return them
    if work_id in _MANUSCRIPT_WORK_MAP:
        return _MANUSCRIPT_WORK_MAP[work_id]
    
    # Reuse scan_docs to find manuscripts for this work
    manuscripts_dir = os.path.join(docs_dir, "manuscripts")
    if os.path.exists(manuscripts_dir):
        results = scan_docs(manuscripts_dir, work_id, "Manuscript", works_included_extractor)
        _MANUSCRIPT_WORK_MAP[work_id] = results
        return results
    return []

def check_manuscript_altered(work_id, docs_dir):
    """Check if a work has an altered manuscript version"""
    global _MANUSCRIPT_CACHE
    
    # Check cache first
    if work_id in _MANUSCRIPT_CACHE:
        return _MANUSCRIPT_CACHE[work_id]
    
    # Get manuscripts for this work (reusing existing scan)
    manuscripts = get_manuscripts_for_work(work_id, docs_dir)
    
    # Check if any have the altered flag
    icon = ""
    for m in manuscripts:
        if m.get("altered"):
            icon = ":material-lead-pencil:{title='Manuscript differs from collected version'}"
            break
    
    _MANUSCRIPT_CACHE[work_id] = icon
    return icon