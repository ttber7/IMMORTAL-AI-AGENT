import json
import os

def notion_to_markdown(blocks_file, output_file):
    with open(blocks_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    markdown = "# PROJECT: IMMORTAL AI AGENT\n\n"
    
    for block in data.get('results', []):
        b_type = block.get('type')
        if b_type == 'paragraph':
            text = "".join([t.get('plain_text', '') for t in block['paragraph'].get('rich_text', [])])
            markdown += f"{text}\n\n"
        elif b_type == 'heading_1':
            text = "".join([t.get('plain_text', '') for t in block['heading_1'].get('rich_text', [])])
            markdown += f"# {text}\n\n"
        elif b_type == 'heading_2':
            text = "".join([t.get('plain_text', '') for t in block['heading_2'].get('rich_text', [])])
            markdown += f"## {text}\n\n"
        elif b_type == 'heading_3':
            text = "".join([t.get('plain_text', '') for t in block['heading_3'].get('rich_text', [])])
            markdown += f"### {text}\n\n"
        elif b_type == 'bulleted_list_item':
            text = "".join([t.get('plain_text', '') for t in block['bulleted_list_item'].get('rich_text', [])])
            markdown += f"* {text}\n"
        elif b_type == 'numbered_list_item':
            text = "".join([t.get('plain_text', '') for t in block['numbered_list_item'].get('rich_text', [])])
            markdown += f"1. {text}\n"
        elif b_type == 'to_do':
            text = "".join([t.get('plain_text', '') for t in block['to_do'].get('rich_text', [])])
            checked = "[x]" if block['to_do'].get('checked') else "[ ]"
            markdown += f"{checked} {text}\n"
        elif b_type == 'callout':
            text = "".join([t.get('plain_text', '') for t in block['callout'].get('rich_text', [])])
            markdown += f"> [!NOTE]\n> {text}\n\n"
        elif b_type == 'divider':
            markdown += "---\n\n"
        elif b_type == 'code':
            text = "".join([t.get('plain_text', '') for t in block['code'].get('rich_text', [])])
            lang = block['code'].get('language', '')
            markdown += f"```{lang}\n{text}\n```\n\n"
            
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(markdown)
    print(f"Markdown saved to {output_file}")

if __name__ == "__main__":
    blocks_path = "C:/Users/Tber/.gemini/antigravity/brain/fb9bcc9b-7590-4777-ba5a-1f3686bdc34d/.system_generated/steps/39/output.txt"
    output_path = "d:/DuAnThg3/THE IMMORTAL AI AGENT/notion_project_notes.md"
    notion_to_markdown(blocks_path, output_path)
