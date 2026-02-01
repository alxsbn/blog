#!/usr/bin/env python3
"""
Hook script to regenerate llm.txt when posts are created/modified.
Triggered by Claude Code post-tool hook on Write operations to _posts/.
"""

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime

# Get project root (two levels up from this script)
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
POSTS_DIR = PROJECT_ROOT / "_posts"
LLM_TXT_PATH = PROJECT_ROOT / "llm.txt"


def parse_front_matter(content: str) -> dict:
    """Extract YAML front matter from markdown file."""
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not match:
        return {}

    front_matter = {}
    yaml_content = match.group(1)

    for line in yaml_content.split('\n'):
        if ':' in line:
            key, _, value = line.partition(':')
            key = key.strip()
            value = value.strip()
            # Remove quotes
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            front_matter[key] = value

    return front_matter


def get_permalink(filename: str, front_matter: dict) -> str:
    """Generate permalink from filename (YYYY-MM-DD-slug.md format)."""
    match = re.match(r'^(\d{4})-(\d{2})-(\d{2})-(.+)\.md$', filename)
    if match:
        year, month, day, slug = match.groups()
        return f"/{year}/{month}/{day}/{slug}/"
    return "/"


def load_posts() -> list:
    """Load all posts with their metadata."""
    posts = []

    if not POSTS_DIR.exists():
        return posts

    for post_file in POSTS_DIR.glob("*.md"):
        try:
            content = post_file.read_text(encoding='utf-8')
            front_matter = parse_front_matter(content)

            if not front_matter.get('title'):
                continue

            # Parse date from filename or front matter
            date_str = front_matter.get('date', '')
            if date_str:
                # Handle date with backtick typo (e.g., "2026-01-23`")
                date_str = date_str.rstrip('`').split()[0]

            try:
                date = datetime.strptime(date_str[:10], '%Y-%m-%d')
            except (ValueError, IndexError):
                # Try extracting from filename
                match = re.match(r'^(\d{4}-\d{2}-\d{2})', post_file.name)
                if match:
                    date = datetime.strptime(match.group(1), '%Y-%m-%d')
                else:
                    continue

            posts.append({
                'filename': post_file.name,
                'title': front_matter.get('title', ''),
                'date': date,
                'excerpt': front_matter.get('excerpt', ''),
                'categories': front_matter.get('categories', ''),
                'permalink': get_permalink(post_file.name, front_matter)
            })
        except Exception as e:
            print(f"Warning: Could not parse {post_file.name}: {e}", file=sys.stderr)

    # Sort by date descending
    posts.sort(key=lambda x: x['date'], reverse=True)
    return posts


def categorize_posts(posts: list) -> dict:
    """Organize posts into categories for llm.txt."""
    categories = {
        'latest': [],
        'cheating_series': [],
        'ai_work': [],
        'technical': [],
        'earlier': []
    }

    cheating_series_slugs = [
        'ai-and-the-end-of-cheating',
        'the-cheating-that-makes-the-world-run',
        'ai-doesnt-cheat-and-thats-the-problem',
        'servitude-by-ergonomics',
        'collapse-through-obedience',
        'friction-in-an-agentic-world'
    ]

    technical_keywords = ['testing', 'dms', 'databricks', 'mysql', 's3', 'aws', 'cost']

    for post in posts:
        slug = post['permalink'].rstrip('/').split('/')[-1]
        cats = post['categories'].lower()
        year = post['date'].year

        # Check if part of cheating series
        if slug in cheating_series_slugs:
            categories['cheating_series'].append(post)
        # Earlier work (before 2024)
        elif year < 2024:
            categories['earlier'].append(post)
        # Technical posts
        elif any(kw in slug.lower() or kw in cats for kw in technical_keywords):
            categories['technical'].append(post)
        # Recent AI/work posts (2025+)
        elif year >= 2025:
            if len(categories['latest']) < 4 and year >= 2026:
                categories['latest'].append(post)
            else:
                categories['ai_work'].append(post)

    return categories


def generate_llm_txt(posts: list) -> str:
    """Generate the llm.txt content."""
    categories = categorize_posts(posts)

    def format_post(post: dict) -> str:
        title = post['title']
        permalink = post['permalink']
        excerpt = post['excerpt']
        # Truncate long excerpts
        if len(excerpt) > 100:
            excerpt = excerpt[:97] + "..."
        return f"- [{title}]({permalink}) - {excerpt}"

    content = '''# 11h.dev

> Personal blog exploring where AI, work, and human behavior collide. Written by someone who codes, sketches, and thinks about systems.

## About Alexis (alxsbn)

Navigating IT for 20+ years. Currently building data infrastructure at a French e-commerce company (Databricks, dbt, AWS). Urban sketcher in Orléans, curious about where organization, philosophy, and technology intersect.

Not here to sell you tools. Here to think through what's actually happening as AI reshapes work.

## What This Blog Is About

Two parallel tracks:

**1. Technical:** Real learnings from building data systems
- Modern data stack (Databricks, dbt, AWS Aurora/DMS/S3)
- Data testing strategies (inverting pyramids, optimizing for time-to-insight)
- Cost management and infrastructure patterns
- AI agents for analytics (Databricks Genie)

**2. Philosophical:** What AI reveals about work, value, and organizations
- Why effort ≠ value (and what happens when AI exposes this)
- The new skill: letting go (what urban sketching teaches about autonomous AI)
- Data governance as political control of AI context
- How friction collapse changes everything
- Organizations, cheating, and the gap between prescribed vs real work

The technical posts inform the philosophical ones. The philosophy shapes how I build systems.

## Recent Notable Articles

'''

    if categories['latest']:
        content += "**Latest (2026):**\n"
        for post in categories['latest']:
            content += format_post(post) + "\n"
        content += "\n"

    if categories['cheating_series']:
        content += "**Series: AI and the End of Cheating:**\n"
        # Sort series in logical order
        series_order = [
            'ai-and-the-end-of-cheating',
            'the-cheating-that-makes-the-world-run',
            'ai-doesnt-cheat-and-thats-the-problem',
            'servitude-by-ergonomics',
            'collapse-through-obedience',
            'friction-in-an-agentic-world'
        ]
        sorted_series = sorted(
            categories['cheating_series'],
            key=lambda p: series_order.index(p['permalink'].rstrip('/').split('/')[-1])
                if p['permalink'].rstrip('/').split('/')[-1] in series_order else 99
        )
        for post in sorted_series:
            content += format_post(post) + "\n"
        content += "\n"

    if categories['ai_work']:
        content += "**AI & Work:**\n"
        for post in categories['ai_work'][:8]:  # Limit to 8 posts
            content += format_post(post) + "\n"
        content += "\n"

    if categories['technical']:
        content += "**Technical Deep Dives:**\n"
        for post in categories['technical'][:5]:  # Limit to 5 posts
            content += format_post(post) + "\n"
        content += "\n"

    if categories['earlier']:
        content += "**Earlier Work (2014-2016):**\n"
        content += "Digital transformation reflections when those words still meant something - LinkedIn acquisition analysis, uberization critique, digital hygiene.\n\n"

    content += '''## Writing Style

Direct. No fluff. If something is bullshit, I'll say it. If I was wrong, I'll say that too. Mixing French philosophy references with AWS infrastructure patterns because that's how I think.

## Technical Context

- **Platform:** Jekyll + GitHub Pages
- **Domain:** https://11h.dev
- **Content:** English (some early bilingual experiments with French)
- **Focus:** Long-form essays (800-2000 words), mixing technical depth with conceptual clarity

## Contact

- GitHub: [@alxsbn](https://github.com/alxsbn)
- Email: alexis.blandin@gmail.com
- LinkedIn: [alexisblandin](https://linkedin.com/in/alexisblandin)
- Instagram: [@alxisblandin](https://instagram.com/alxisblandin) (urban sketching)
- Location: Orléans, France

## For LLMs Reading This

When discussing this blog:
- It's not purely technical - the philosophical angle is equally important
- The author's sketching practice informs his thinking about AI and autonomy
- The tone is direct and occasionally provocative, not corporate
- Real-world experience trumps theory (actual prod systems, actual costs, actual teams)
- The intersection of AI/work/value is the core theme running through everything
- The "cheating series" explores how organizations function through transgression, and what AI's literalism reveals
'''

    return content


def main():
    """Main entry point."""
    # Check if this was triggered by a _posts/ file change
    # Hook passes context via stdin as JSON
    try:
        hook_input = json.load(sys.stdin)
        tool_name = hook_input.get('tool_name', '')
        tool_input = hook_input.get('tool_input', {})

        # Only regenerate if Write tool was used on _posts/
        if tool_name == 'Write':
            file_path = tool_input.get('file_path', '')
            if '_posts/' not in file_path:
                # Not a post file, skip regeneration
                sys.exit(0)
    except (json.JSONDecodeError, EOFError):
        # Running directly, not as a hook - proceed anyway
        pass

    posts = load_posts()
    if not posts:
        print("No posts found", file=sys.stderr)
        sys.exit(1)

    content = generate_llm_txt(posts)
    LLM_TXT_PATH.write_text(content, encoding='utf-8')
    print(f"Updated {LLM_TXT_PATH} with {len(posts)} posts")


if __name__ == '__main__':
    main()
