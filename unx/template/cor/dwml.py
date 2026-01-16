"""
DWML (DontWorry Markup Language) Parser
Version: 1.0

Reference implementation for parsing and creating DWML documents.
"""

import re
from typing import Dict, List, Optional, Any, Union


# Block patterns
BLOCK_OPEN = re.compile(r'=d=(\w+)=w=')
BLOCK_CLOSE = re.compile(r'=q=(\w+)=e=')

# Container patterns
CONTAINER_OPEN = '=dw='
CONTAINER_CLOSE = '=wd='

# Inline patterns
CONTENT_PATTERN = re.compile(r'=x=\s*(.*?)\s*=z=')
COMMENT_PATTERN = re.compile(r'=#=(.*?)=o=')
ADDED_PATTERN = re.compile(r'=\+=(.*?)=o=')
REMOVED_PATTERN = re.compile(r'=-=(.*?)=o=')

# Value patterns
VALUE_PATTERN = re.compile(r'(\w+);\|([^|]*)\|;')
VALUE_LIST_PATTERN = re.compile(r';\|([^|]*)\|;')


class DWMLBlock:
    """Represents a DWML block with name and content"""

    def __init__(self, name: str):
        self.name = name
        self.fields: Dict[str, Any] = {}
        self.containers: List['DWMLContainer'] = []
        self.comments: List[str] = []
        self.raw_lines: List[str] = []

    def get(self, key: str, default: str = "") -> str:
        """Get single value for key"""
        value = self.fields.get(key, default)
        if isinstance(value, list):
            return value[0] if value else default
        return value

    def get_list(self, key: str) -> List[str]:
        """Get list of values for key"""
        value = self.fields.get(key, [])
        if isinstance(value, list):
            return value
        return [value] if value else []

    def set(self, key: str, value: Union[str, List[str]]):
        """Set value for key"""
        self.fields[key] = value

    def add_container(self, container: 'DWMLContainer'):
        """Add a container to this block"""
        self.containers.append(container)


class DWMLContainer:
    """Represents a =dw=...=wd= container"""

    def __init__(self):
        self.fields: Dict[str, Any] = {}
        self.added: List[str] = []
        self.removed: List[str] = []
        self.comments: List[str] = []
        self.raw_lines: List[str] = []

    def get(self, key: str, default: str = "") -> str:
        """Get single value for key"""
        value = self.fields.get(key, default)
        if isinstance(value, list):
            return value[0] if value else default
        return value

    def get_list(self, key: str) -> List[str]:
        """Get list of values for key"""
        value = self.fields.get(key, [])
        if isinstance(value, list):
            return value
        return [value] if value else []


class DWML:
    """DWML document parser and builder"""

    def __init__(self):
        self.blocks: Dict[str, DWMLBlock] = {}
        self.block_order: List[str] = []

    @classmethod
    def parse(cls, content: str) -> 'DWML':
        """Parse DWML content string into document"""
        doc = cls()
        doc._parse_content(content)
        return doc

    @classmethod
    def parse_file(cls, filepath: str) -> 'DWML':
        """Parse DWML file into document"""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        return cls.parse(content)

    def _parse_content(self, content: str):
        """Internal parsing logic"""
        # Find all blocks
        block_pattern = re.compile(
            r'=d=(\w+)=w=(.*?)=q=\1=e=',
            re.DOTALL
        )

        for match in block_pattern.finditer(content):
            name = match.group(1)
            block_content = match.group(2)

            block = DWMLBlock(name)
            self._parse_block_content(block, block_content)

            self.blocks[name] = block
            self.block_order.append(name)

    def _parse_block_content(self, block: DWMLBlock, content: str):
        """Parse content inside a block"""
        # Check for containers
        container_pattern = re.compile(
            r'=dw=(.*?)=wd=',
            re.DOTALL
        )

        containers = list(container_pattern.finditer(content))

        if containers:
            # Parse each container
            for match in containers:
                container = DWMLContainer()
                self._parse_container_content(container, match.group(1))
                block.add_container(container)

            # Also parse non-container content at block level
            remaining = container_pattern.sub('', content)
            self._parse_fields(block, remaining)
        else:
            # No containers, parse directly
            self._parse_fields(block, content)

    def _parse_container_content(self, container: DWMLContainer, content: str):
        """Parse content inside a container"""
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue

            # Check for comments
            comment_match = COMMENT_PATTERN.search(line)
            if comment_match:
                container.comments.append(comment_match.group(1).strip())
                continue

            # Check for added lines
            added_match = ADDED_PATTERN.search(line)
            if added_match:
                container.added.append(added_match.group(1).strip())
                continue

            # Check for removed lines
            removed_match = REMOVED_PATTERN.search(line)
            if removed_match:
                container.removed.append(removed_match.group(1).strip())
                continue

            # Check for content
            content_match = CONTENT_PATTERN.search(line)
            if content_match:
                self._parse_value_line(container.fields, content_match.group(1))
                continue

            container.raw_lines.append(line)

    def _parse_fields(self, target: Union[DWMLBlock, DWMLContainer], content: str):
        """Parse field content into target"""
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue

            # Check for comments
            comment_match = COMMENT_PATTERN.search(line)
            if comment_match:
                if isinstance(target, DWMLBlock):
                    target.comments.append(comment_match.group(1).strip())
                continue

            # Check for content
            content_match = CONTENT_PATTERN.search(line)
            if content_match:
                self._parse_value_line(target.fields, content_match.group(1))
                continue

            target.raw_lines.append(line)

    def _parse_value_line(self, fields: Dict, line: str):
        """Parse key;|value|; patterns from line"""
        # Find all key;|value|; pairs
        for match in VALUE_PATTERN.finditer(line):
            key = match.group(1)
            value = match.group(2)

            # Check if key already exists (multiple values)
            if key in fields:
                existing = fields[key]
                if isinstance(existing, list):
                    existing.append(value)
                else:
                    fields[key] = [existing, value]
            else:
                fields[key] = value

        # Handle list values with comma separator
        # Pattern: key;|val1|;,;|val2|;,;|val3|;
        list_pattern = re.compile(r'(\w+)((?:;\|[^|]*\|;,?)+)')
        for match in list_pattern.finditer(line):
            key = match.group(1)
            values_str = match.group(2)
            values = VALUE_LIST_PATTERN.findall(values_str)
            if len(values) > 1:
                fields[key] = values

    def block(self, name: str) -> Optional[DWMLBlock]:
        """Get block by name"""
        return self.blocks.get(name)

    def has_block(self, name: str) -> bool:
        """Check if block exists"""
        return name in self.blocks

    def add_block(self, name: str, fields: Optional[Dict[str, Any]] = None) -> DWMLBlock:
        """Add new block to document"""
        block = DWMLBlock(name)
        if fields:
            for key, value in fields.items():
                block.set(key, value)
        self.blocks[name] = block
        self.block_order.append(name)
        return block

    def render(self) -> str:
        """Render document to DWML string"""
        lines = []

        for name in self.block_order:
            block = self.blocks[name]
            lines.append(f'=d={name}=w=')

            # Render comments
            for comment in block.comments:
                lines.append(f'=#= {comment} =o=')

            # Render fields
            for key, value in block.fields.items():
                if isinstance(value, list):
                    values_str = ','.join(f';|{v}|;' for v in value)
                    lines.append(f'=x= {key}{values_str} =z=')
                else:
                    lines.append(f'=x= {key};|{value}|; =z=')

            # Render containers
            for container in block.containers:
                lines.append('=dw=')

                for comment in container.comments:
                    lines.append(f'=#= {comment} =o=')

                for key, value in container.fields.items():
                    if isinstance(value, list):
                        values_str = ','.join(f';|{v}|;' for v in value)
                        lines.append(f'=x= {key}{values_str} =z=')
                    else:
                        lines.append(f'=x= {key};|{value}|; =z=')

                for added in container.added:
                    lines.append(f'=+= {added} =o=')

                for removed in container.removed:
                    lines.append(f'=-= {removed} =o=')

                lines.append('=wd=')

            lines.append(f'=q={name}=e=')

        return '\n'.join(lines)

    def save(self, filepath: str):
        """Save document to file"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.render())


# Convenience functions for simple operations

def parse(content: str) -> DWML:
    """Parse DWML content string"""
    return DWML.parse(content)


def parse_file(filepath: str) -> DWML:
    """Parse DWML file"""
    return DWML.parse_file(filepath)


def has_block(content: str, name: str) -> bool:
    """Check if content has block with name"""
    pattern = re.compile(rf'=d={name}=w=.*?=q={name}=e=', re.DOTALL)
    return bool(pattern.search(content))


def get_block_content(content: str, name: str) -> str:
    """Extract raw content between block tags"""
    pattern = re.compile(rf'=d={name}=w=(.*?)=q={name}=e=', re.DOTALL)
    match = pattern.search(content)
    return match.group(1).strip() if match else ""


def get_field(content: str, block_name: str, field: str) -> str:
    """Get single field value from block"""
    doc = DWML.parse(content)
    block = doc.block(block_name)
    if block:
        return block.get(field)
    return ""


def create_block(name: str, fields: Dict[str, Any], comments: List[str] = None) -> str:
    """Create a single block string"""
    lines = [f'=d={name}=w=']

    if comments:
        for comment in comments:
            lines.append(f'=#= {comment} =o=')

    for key, value in fields.items():
        if isinstance(value, list):
            values_str = ','.join(f';|{v}|;' for v in value)
            lines.append(f'=x= {key}{values_str} =z=')
        else:
            lines.append(f'=x= {key};|{value}|; =z=')

    lines.append(f'=q={name}=e=')

    return '\n'.join(lines)


def create_container(fields: Dict[str, Any] = None, added: List[str] = None,
                     removed: List[str] = None, comments: List[str] = None) -> str:
    """Create a container string"""
    lines = ['=dw=']

    if comments:
        for comment in comments:
            lines.append(f'=#= {comment} =o=')

    if fields:
        for key, value in fields.items():
            if isinstance(value, list):
                values_str = ','.join(f';|{v}|;' for v in value)
                lines.append(f'=x= {key}{values_str} =z=')
            else:
                lines.append(f'=x= {key};|{value}|; =z=')

    if added:
        for line in added:
            lines.append(f'=+= {line} =o=')

    if removed:
        for line in removed:
            lines.append(f'=-= {line} =o=')

    lines.append('=wd=')

    return '\n'.join(lines)


def update_field(content: str, block_name: str, field: str, value: Union[str, List[str]]) -> str:
    """Update field in content, return new content"""
    doc = DWML.parse(content)
    block = doc.block(block_name)

    if block:
        block.set(field, value)
        # Find and replace the block in original content
        old_block_pattern = re.compile(
            rf'=d={block_name}=w=.*?=q={block_name}=e=',
            re.DOTALL
        )

        # Render just this block
        new_block_lines = [f'=d={block_name}=w=']
        for comment in block.comments:
            new_block_lines.append(f'=#= {comment} =o=')
        for k, v in block.fields.items():
            if isinstance(v, list):
                values_str = ','.join(f';|{val}|;' for val in v)
                new_block_lines.append(f'=x= {k}{values_str} =z=')
            else:
                new_block_lines.append(f'=x= {k};|{v}|; =z=')
        for container in block.containers:
            new_block_lines.append('=dw=')
            for comment in container.comments:
                new_block_lines.append(f'=#= {comment} =o=')
            for k, v in container.fields.items():
                if isinstance(v, list):
                    values_str = ','.join(f';|{val}|;' for val in v)
                    new_block_lines.append(f'=x= {k}{values_str} =z=')
                else:
                    new_block_lines.append(f'=x= {k};|{v}|; =z=')
            for a in container.added:
                new_block_lines.append(f'=+= {a} =o=')
            for r in container.removed:
                new_block_lines.append(f'=-= {r} =o=')
            new_block_lines.append('=wd=')
        new_block_lines.append(f'=q={block_name}=e=')

        new_block = '\n'.join(new_block_lines)
        return old_block_pattern.sub(new_block, content)

    return content
