# app.py - Flask application with enhanced database viewer
from flask import Flask, render_template_string, jsonify
import sqlite3
import json
import html
from collections import defaultdict

app = Flask(__name__)
DB_FILE = 'config.db'

# ==============================================
# DATABASE INITIALIZATION
# ==============================================

def init_database():
    """Initialize SQLite database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Check if database exists and has tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    if not tables:
        print("Database not initialized. Run database.py first.")
        return False
    
    conn.close()
    return True

# ==============================================
# HELPER FUNCTIONS
# ==============================================

def get_table_schema():
    """Get complete schema information for all tables"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    schema = {}
    relationships = []
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    for table in tables:
        # Get columns
        cursor.execute(f"PRAGMA table_info({table})")
        columns = []
        for col in cursor.fetchall():
            columns.append({
                'name': col[1],
                'type': col[2],
                'not_null': bool(col[3]),
                'default': col[4],
                'pk': bool(col[5])
            })
        
        # Get foreign keys
        cursor.execute(f"PRAGMA foreign_key_list({table})")
        fks = []
        for fk in cursor.fetchall():
            fks.append({
                'from_column': fk[3],
                'to_table': fk[2],
                'to_column': fk[4]
            })
            relationships.append({
                'from_table': table,
                'from_column': fk[3],
                'to_table': fk[2],
                'to_column': fk[4]
            })
        
        # Get indexes
        cursor.execute(f"PRAGMA index_list({table})")
        indexes = []
        for idx in cursor.fetchall():
            if idx[2]:  # unique index
                cursor.execute(f"PRAGMA index_info({idx[1]})")
                idx_cols = [row[2] for row in cursor.fetchall()]
                indexes.append({
                    'name': idx[1],
                    'columns': idx_cols,
                    'unique': bool(idx[2])
                })
        
        schema[table] = {
            'columns': columns,
            'foreign_keys': fks,
            'indexes': indexes,
            'row_count': get_row_count(cursor, table)
        }
    
    conn.close()
    return schema, relationships, tables

def get_row_count(cursor, table):
    """Get row count for a table"""
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        return cursor.fetchone()[0]
    except:
        return 0

def get_table_data(table_name, limit=100):
    """Get data from a table"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
        rows = cursor.fetchall()
        data = [dict(row) for row in rows]
        
        # Get column names for this table
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in cursor.fetchall()]
        
        conn.close()
        return data, columns
    except Exception as e:
        conn.close()
        return [], []

# ==============================================
# ENHANCED DATABASE VIEWER
# ==============================================

@app.route('/db')
def database_viewer():
    """Enhanced database viewer with proper ER diagram"""
    try:
        # Get schema information
        schema, relationships, tables = get_table_schema()
        
        # Generate enhanced ER diagram
        er_diagram = generate_enhanced_er_diagram(schema, relationships, tables)
        
        # Generate HTML
        html_content = generate_enhanced_html(schema, relationships, tables, er_diagram)
        
        return render_template_string(html_content)
    
    except Exception as e:
        return f"<h1>Database Error</h1><p>{str(e)}</p>", 500

def generate_enhanced_er_diagram(schema, relationships, tables):
    """Generate a proper ER diagram based on database schema"""
    
    # Define table categories for grouping
    table_categories = defaultdict(list)
    
    # Categorize tables based on name patterns
    for table in tables:
        table_lower = table.lower()
        if 'config' in table_lower:
            table_categories['configuration'].append(table)
        elif 'service' in table_lower:
            table_categories['services'].append(table)
        elif 'group' in table_lower:
            table_categories['groups'].append(table)
        elif 'modbus' in table_lower:
            table_categories['modbus'].append(table)
        elif 'loadcell' in table_lower or 'load_cell' in table_lower:
            table_categories['loadcell'].append(table)
        elif 'device' in table_lower:
            table_categories['devices'].append(table)
        elif 'point' in table_lower or 'data' in table_lower:
            table_categories['datapoints'].append(table)
        else:
            table_categories['other'].append(table)
    
    # Calculate positions based on categories
    category_positions = {
        'configuration': {'x': 50, 'y': 50, 'color': '#3498db'},
        'services': {'x': 300, 'y': 50, 'color': '#2ecc71'},
        'groups': {'x': 550, 'y': 50, 'color': '#e74c3c'},
        'modbus': {'x': 50, 'y': 300, 'color': '#9b59b6'},
        'loadcell': {'x': 300, 'y': 300, 'color': '#f39c12'},
        'devices': {'x': 550, 'y': 300, 'color': '#1abc9c'},
        'datapoints': {'x': 50, 'y': 550, 'color': '#34495e'},
        'other': {'x': 300, 'y': 550, 'color': '#7f8c8d'}
    }
    
    # Calculate total width needed
    max_category_width = 0
    for category, tables_in_cat in table_categories.items():
        if tables_in_cat:
            category_width = 280  # base width
            category_height = 40 + (len(tables_in_cat) * 120)
            if category_width > max_category_width:
                max_category_width = category_width
    
    # Adjust positions to ensure no overlap
    adjusted_positions = {}
    current_x = 50
    current_y = 50
    row_height = 0
    
    for category, tables_in_cat in table_categories.items():
        if tables_in_cat:
            category_height = 40 + (len(tables_in_cat) * 120)
            
            # Check if we need to move to next row
            if current_x + max_category_width > 1000:  # canvas width
                current_x = 50
                current_y += row_height + 50
                row_height = 0
            
            adjusted_positions[category] = {
                'x': current_x,
                'y': current_y,
                'color': category_positions.get(category, {}).get('color', '#3498db')
            }
            
            if category_height > row_height:
                row_height = category_height
            
            current_x += max_category_width + 30
    
    diagram_html = '''
    <div class="er-diagram-container">
        <div class="er-canvas" id="erCanvas">
    '''
    
    # Draw each category
    for category, position in adjusted_positions.items():
        category_tables = table_categories.get(category, [])
        
        if category_tables:
            # Draw category box
            category_height = 40 + (len(category_tables) * 120)
            diagram_html += f'''
            <div class="category-box" style="left: {position['x']}px; top: {position['y']}px; border-color: {position['color']}20; background: {position['color']}10;">
                <div class="category-header" style="background: {position['color']};">
                    <span>{category.upper()}</span>
                    <span class="table-count">({len(category_tables)})</span>
                </div>
            '''
            
            # Draw tables in this category
            for i, table in enumerate(category_tables):
                table_info = schema.get(table, {})
                table_x = 10
                table_y = 40 + (i * 120)
                
                diagram_html += generate_table_node(table, table_info, table_x, table_y, position['color'])
            
            diagram_html += '</div>'
    
    # Draw relationships
    if relationships:
        diagram_html += '<svg class="relationship-lines">'
        
        for rel in relationships:
            # Find source and target table positions
            from_table_pos = find_table_position(rel['from_table'], table_categories, adjusted_positions)
            to_table_pos = find_table_position(rel['to_table'], table_categories, adjusted_positions)
            
            if from_table_pos and to_table_pos:
                # Calculate line coordinates
                from_center_x = from_table_pos['x'] + 150  # Center of table node
                from_center_y = from_table_pos['y'] + 20   # Top of table node
                to_center_x = to_table_pos['x'] + 150
                to_center_y = to_table_pos['y'] + 20
                
                # Draw relationship line with curved path for better visibility
                mid_x = (from_center_x + to_center_x) / 2
                mid_y = (from_center_y + to_center_y) / 2
                
                # Add some curve to avoid overlapping
                control_x1 = from_center_x + (to_center_x - from_center_x) / 3
                control_y1 = from_center_y - 50
                control_x2 = to_center_x - (to_center_x - from_center_x) / 3
                control_y2 = to_center_y - 50
                
                diagram_html += f'''
                <path d="M {from_center_x} {from_center_y} 
                         C {control_x1} {control_y1}, {control_x2} {control_y2}, {to_center_x} {to_center_y}"
                      class="relationship-line" 
                      data-from="{rel['from_table']}.{rel['from_column']}"
                      data-to="{rel['to_table']}.{rel['to_column']}" />
                
                <circle cx="{from_center_x}" cy="{from_center_y}" r="4" class="relationship-dot from-dot" />
                <circle cx="{to_center_x}" cy="{to_center_y}" r="4" class="relationship-dot to-dot" />
                '''
        
        diagram_html += '</svg>'
    
    diagram_html += '</div></div>'
    
    return diagram_html

def generate_table_node(table_name, table_info, x, y, color):
    """Generate HTML for a table node in ER diagram"""
    columns = table_info.get('columns', [])
    row_count = table_info.get('row_count', 0)
    
    # Count primary keys and foreign keys
    pk_count = sum(1 for col in columns if col.get('pk', False))
    fk_count = len(table_info.get('foreign_keys', []))
    
    # Generate column list HTML (limited to 5 for compact view)
    columns_html = ''
    display_columns = columns[:5]  # Show first 5 columns
    for col in display_columns:
        col_class = ''
        if col.get('pk'):
            col_class = 'pk-column'
        elif any(fk['from_column'] == col['name'] for fk in table_info.get('foreign_keys', [])):
            col_class = 'fk-column'
        
        col_name = col['name'][:15] + '...' if len(col['name']) > 15 else col['name']
        col_type = col['type'][:10] if col['type'] else ''
        
        columns_html += f'''
        <div class="column-item {col_class}">
            <span class="column-name" title="{col['name']}">{col_name}</span>
            <span class="column-type">{col_type}</span>
        </div>
        '''
    
    if len(columns) > 5:
        columns_html += f'<div class="column-more">+ {len(columns)-5} more</div>'
    
    return f'''
    <div class="table-node" style="left: {x}px; top: {y}px; border-color: {color};" 
         data-table="{table_name}" title="Click to view data">
        <div class="table-header" style="background: {color};">
            <span class="table-name">{table_name[:20]}{'...' if len(table_name) > 20 else ''}</span>
            <span class="table-stats">
                <span class="stat-badge rows" title="{row_count} rows">{row_count}</span>
                {f'<span class="stat-badge pk" title="{pk_count} primary keys">{pk_count}</span>' if pk_count > 0 else ''}
                {f'<span class="stat-badge fk" title="{fk_count} foreign keys">{fk_count}</span>' if fk_count > 0 else ''}
            </span>
        </div>
        <div class="table-columns">
            {columns_html}
        </div>
    </div>
    '''

def find_table_position(table_name, table_categories, category_positions):
    """Find position of a table in the diagram"""
    for category, tables in table_categories.items():
        if table_name in tables:
            base_pos = category_positions.get(category, {'x': 0, 'y': 0})
            # Calculate specific position within category
            index = tables.index(table_name)
            return {
                'x': base_pos['x'] + 10,
                'y': base_pos['y'] + 40 + (index * 120)
            }
    return None

def generate_enhanced_html(schema, relationships, tables, er_diagram):
    """Generate enhanced HTML with proper ER diagram"""
    
    # CSS Styles for enhanced viewer (with compact design)
    styles = '''
    <style>
        :root {
            --primary-color: #3498db;
            --secondary-color: #2c3e50;
            --success-color: #27ae60;
            --danger-color: #e74c3c;
            --warning-color: #f39c12;
            --light-color: #f8f9fa;
            --dark-color: #343a40;
            --border-radius: 8px;
            --shadow: 0 4px 12px rgba(0,0,0,0.1);
            --transition: all 0.2s ease;
        }
        
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #f5f7fa 0%, #e4e8f0 100%);
            min-height: 100vh;
            padding: 15px;
            color: #333;
            font-size: 14px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        /* Header */
        .main-header {
            background: white;
            padding: 20px;
            border-radius: var(--border-radius);
            box-shadow: var(--shadow);
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
        }
        
        .header-title h1 {
            color: var(--secondary-color);
            margin-bottom: 8px;
            font-size: 1.8em;
            font-weight: 600;
        }
        
        .header-title p {
            color: #7f8c8d;
            font-size: 0.95em;
        }
        
        .header-stats {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }
        
        .stat-item {
            text-align: center;
            padding: 12px 20px;
            background: var(--light-color);
            border-radius: var(--border-radius);
            min-width: 100px;
        }
        
        .stat-value {
            display: block;
            font-size: 1.5em;
            font-weight: bold;
            color: var(--primary-color);
            margin-bottom: 4px;
        }
        
        .stat-label {
            color: #7f8c8d;
            font-size: 0.85em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        /* Navigation */
        .nav-tabs {
            display: flex;
            gap: 8px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        
        .nav-tab {
            padding: 12px 20px;
            background: white;
            border: none;
            border-radius: var(--border-radius);
            cursor: pointer;
            font-weight: 600;
            color: var(--dark-color);
            transition: var(--transition);
            display: flex;
            align-items: center;
            gap: 8px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.05);
            font-size: 0.95em;
        }
        
        .nav-tab:hover {
            background: var(--light-color);
            transform: translateY(-1px);
        }
        
        .nav-tab.active {
            background: var(--primary-color);
            color: white;
            box-shadow: 0 3px 10px rgba(52, 152, 219, 0.3);
        }
        
        /* ER Diagram Container */
        .er-diagram-container {
            background: white;
            border-radius: var(--border-radius);
            box-shadow: var(--shadow);
            margin-bottom: 20px;
            padding: 15px;
            position: relative;
            min-height: 600px;
            overflow: auto;
            border: 1px solid #e9ecef;
        }
        
        .er-canvas {
            position: relative;
            min-height: 600px;
            width: 1100px;
        }
        
        /* Category Box */
        .category-box {
            position: absolute;
            background: rgba(248, 249, 250, 0.9);
            border: 1px solid;
            border-radius: var(--border-radius);
            padding: 8px;
            min-width: 280px;
        }
        
        .category-header {
            color: white;
            padding: 8px 12px;
            border-radius: 6px;
            font-weight: bold;
            text-align: center;
            margin-bottom: 8px;
            font-size: 0.9em;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .table-count {
            font-size: 0.85em;
            opacity: 0.9;
        }
        
        /* Table Node */
        .table-node {
            position: absolute;
            background: white;
            border: 2px solid;
            border-radius: 6px;
            padding: 0;
            width: 260px;
            box-shadow: 0 3px 10px rgba(0,0,0,0.08);
            transition: var(--transition);
            z-index: 10;
            cursor: pointer;
        }
        
        .table-node:hover {
            transform: scale(1.03);
            box-shadow: 0 8px 20px rgba(0,0,0,0.15);
            z-index: 100;
        }
        
        .table-header {
            color: white;
            padding: 10px 12px;
            border-radius: 4px 4px 0 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.9em;
        }
        
        .table-name {
            font-weight: bold;
        }
        
        .table-stats {
            display: flex;
            gap: 4px;
        }
        
        .stat-badge {
            padding: 2px 6px;
            border-radius: 10px;
            font-size: 0.75em;
            font-weight: bold;
            min-width: 20px;
            text-align: center;
        }
        
        .stat-badge.rows {
            background: var(--success-color);
            color: white;
        }
        
        .stat-badge.pk {
            background: var(--danger-color);
            color: white;
        }
        
        .stat-badge.fk {
            background: var(--warning-color);
            color: white;
        }
        
        .table-columns {
            padding: 8px;
            max-height: 180px;
            overflow-y: auto;
        }
        
        .column-item {
            padding: 5px 6px;
            border-bottom: 1px solid #eee;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 0.85em;
            display: flex;
            justify-content: space-between;
        }
        
        .column-item:last-child {
            border-bottom: none;
        }
        
        .column-item.pk-column {
            background: rgba(231, 76, 60, 0.08);
            border-left: 2px solid var(--danger-color);
        }
        
        .column-item.fk-column {
            background: rgba(52, 152, 219, 0.08);
            border-left: 2px solid var(--primary-color);
        }
        
        .column-name {
            font-weight: 600;
            color: var(--secondary-color);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            max-width: 150px;
        }
        
        .column-type {
            color: #7f8c8d;
            font-size: 0.8em;
        }
        
        .column-more {
            text-align: center;
            padding: 6px;
            color: var(--primary-color);
            font-style: italic;
            font-size: 0.85em;
            background: #f8f9fa;
            border-radius: 4px;
            margin-top: 4px;
        }
        
        /* Relationship Lines */
        .relationship-lines {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 1;
        }
        
        .relationship-line {
            stroke: #95a5a6;
            stroke-width: 1.5;
            stroke-dasharray: 4,4;
            fill: none;
            transition: var(--transition);
        }
        
        .relationship-line:hover {
            stroke: var(--warning-color);
            stroke-width: 2;
            stroke-dasharray: none;
        }
        
        .relationship-dot {
            fill: white;
            stroke-width: 2;
            transition: var(--transition);
        }
        
        .relationship-dot.from-dot {
            stroke: var(--danger-color);
        }
        
        .relationship-dot.to-dot {
            stroke: var(--success-color);
        }
        
        /* Table Details Section */
        .table-details-section {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(450px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .table-card {
            background: white;
            border-radius: var(--border-radius);
            box-shadow: var(--shadow);
            overflow: hidden;
            transition: var(--transition);
        }
        
        .table-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.1);
        }
        
        .table-card-header {
            background: var(--secondary-color);
            color: white;
            padding: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .table-card-title {
            font-size: 1.1em;
            font-weight: bold;
        }
        
        .table-card-stats {
            display: flex;
            gap: 8px;
        }
        
        .schema-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9em;
        }
        
        .schema-table th {
            background: var(--light-color);
            padding: 10px 12px;
            text-align: left;
            font-weight: 600;
            color: var(--dark-color);
            border-bottom: 2px solid #dee2e6;
            font-size: 0.9em;
        }
        
        .schema-table td {
            padding: 8px 12px;
            border-bottom: 1px solid #e9ecef;
            font-family: 'Consolas', 'Courier New', monospace;
        }
        
        .schema-table tr:hover {
            background: rgba(52, 152, 219, 0.05);
        }
        
        .key-badge {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.75em;
            font-weight: bold;
            margin-right: 4px;
        }
        
        .pk-badge {
            background: var(--danger-color);
            color: white;
        }
        
        .fk-badge {
            background: var(--primary-color);
            color: white;
        }
        
        .uk-badge {
            background: var(--success-color);
            color: white;
        }
        
        /* Data Viewer */
        .data-viewer {
            background: white;
            border-radius: var(--border-radius);
            box-shadow: var(--shadow);
            padding: 20px;
            margin-bottom: 20px;
        }
        
        .data-table-container {
            overflow-x: auto;
            margin-top: 16px;
            max-height: 400px;
            overflow-y: auto;
        }
        
        .data-table {
            width: 100%;
            border-collapse: collapse;
            min-width: 700px;
            font-size: 0.9em;
        }
        
        .data-table th {
            background: var(--secondary-color);
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            position: sticky;
            top: 0;
            z-index: 10;
            font-size: 0.9em;
        }
        
        .data-table td {
            padding: 10px 12px;
            border-bottom: 1px solid #e9ecef;
            vertical-align: top;
        }
        
        .data-table tr:nth-child(even) {
            background: var(--light-color);
        }
        
        .data-table tr:hover {
            background: rgba(52, 152, 219, 0.1);
        }
        
        .json-cell {
            max-width: 250px;
            max-height: 80px;
            overflow: auto;
        }
        
        .json-pre {
            background: #f8f9fa;
            padding: 6px;
            border-radius: 4px;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 0.85em;
            margin: 0;
            white-space: pre-wrap;
            word-break: break-all;
        }
        
        /* Controls */
        .controls {
            display: flex;
            gap: 12px;
            margin-bottom: 16px;
            flex-wrap: wrap;
        }
        
        .control-group {
            display: flex;
            gap: 8px;
            align-items: center;
        }
        
        select, input, button {
            padding: 8px 12px;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            font-size: 0.9em;
            transition: var(--transition);
        }
        
        select:focus, input:focus {
            outline: none;
            border-color: var(--primary-color);
            box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1);
        }
        
        .btn {
            padding: 8px 16px;
            background: var(--primary-color);
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 6px;
            transition: var(--transition);
            font-size: 0.9em;
        }
        
        .btn:hover {
            background: #2980b9;
            transform: translateY(-1px);
        }
        
        .btn-secondary {
            background: #6c757d;
        }
        
        .btn-secondary:hover {
            background: #545b62;
        }
        
        /* Empty State */
        .empty-state {
            text-align: center;
            padding: 40px 20px;
            color: #7f8c8d;
        }
        
        .empty-state i {
            font-size: 2.5em;
            margin-bottom: 16px;
            color: #dee2e6;
        }
        
        .empty-state h3 {
            font-size: 1.2em;
            margin-bottom: 8px;
        }
        
        /* Responsive */
        @media (max-width: 1200px) {
            .er-diagram-container {
                overflow-x: auto;
            }
            
            .er-canvas {
                width: 900px;
            }
        }
        
        @media (max-width: 768px) {
            .main-header {
                flex-direction: column;
                text-align: center;
            }
            
            .header-stats {
                justify-content: center;
            }
            
            .nav-tabs {
                flex-direction: column;
            }
            
            .table-details-section {
                grid-template-columns: 1fr;
            }
            
            .er-canvas {
                width: 700px;
            }
            
            .controls {
                flex-direction: column;
            }
            
            .control-group {
                width: 100%;
            }
            
            select, input {
                flex-grow: 1;
            }
        }
        
        /* Animations */
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .fade-in {
            animation: fadeIn 0.3s ease;
        }
        
        /* Highlight for search */
        mark {
            background: #fff3cd;
            color: #856404;
            padding: 1px 3px;
            border-radius: 3px;
        }
        
        /* Scrollbar styling */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: #f1f1f1;
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb {
            background: #c1c1c1;
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: #a8a8a8;
        }
    </style>
    '''
    
    # JavaScript for interactivity
    scripts = '''
    <script>
        // Tab switching
        function showTab(tabId) {
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
                tab.style.display = 'none';
            });
            
            // Remove active class from all tab buttons
            document.querySelectorAll('.nav-tab').forEach(btn => {
                btn.classList.remove('active');
            });
            
            // Show selected tab
            const selectedTab = document.getElementById(tabId);
            if (selectedTab) {
                selectedTab.classList.add('active');
                selectedTab.style.display = 'block';
            }
            
            // Activate clicked button
            event.currentTarget.classList.add('active');
            
            // Save active tab
            localStorage.setItem('activeTab', tabId);
        }
        
        // Table selection for data viewer
        function selectTable(tableName) {
            document.getElementById('selectedTable').value = tableName;
            loadTableData(tableName);
        }
        
        function loadTableData(tableName) {
            if (!tableName) return;
            
            fetch(`/api/db/table/${tableName}`)
                .then(response => response.json())
                .then(data => {
                    displayTableData(data);
                })
                .catch(error => {
                    console.error('Error loading table data:', error);
                    document.getElementById('dataTableContainer').innerHTML = 
                        '<div class="empty-state"><i class="fas fa-exclamation-circle"></i><h3>Error loading data</h3></div>';
                });
        }
        
        function displayTableData(data) {
            const container = document.getElementById('dataTableContainer');
            if (!data.data || data.data.length === 0) {
                container.innerHTML = '<div class="empty-state"><i class="fas fa-database"></i><h3>No data found</h3></div>';
                return;
            }
            
            const columns = Object.keys(data.data[0]);
            let html = `
                <div class="data-table-container">
                    <table class="data-table">
                        <thead>
                            <tr>
                                ${columns.map(col => `<th>${escapeHtml(col)}</th>`).join('')}
                            </tr>
                        </thead>
                        <tbody>
            `;
            
            data.data.forEach(row => {
                html += '<tr>';
                columns.forEach(col => {
                    let value = row[col];
                    let displayValue = value;
                    
                    if (value === null || value === undefined) {
                        displayValue = '<span style="color: #999; font-style: italic;">NULL</span>';
                    } else if (typeof value === 'object') {
                        displayValue = `<div class="json-cell"><pre class="json-pre">${escapeHtml(JSON.stringify(value, null, 2))}</pre></div>`;
                    } else if (typeof value === 'boolean') {
                        displayValue = value ? '<span style="color: #28a745; font-weight: bold;">TRUE</span>' : 
                                             '<span style="color: #dc3545; font-weight: bold;">FALSE</span>';
                    } else if (typeof value === 'number') {
                        displayValue = `<span style="color: #17a2b8;">${value}</span>`;
                    } else {
                        displayValue = escapeHtml(String(value));
                        if (displayValue.length > 100) {
                            displayValue = displayValue.substring(0, 100) + '...';
                        }
                    }
                    
                    html += `<td>${displayValue}</td>`;
                });
                html += '</tr>';
            });
            
            html += `
                        </tbody>
                    </table>
                </div>
                <div style="margin-top: 12px; color: #6c757d; font-size: 0.9em;">
                    Showing ${data.data.length} rows
                </div>
            `;
            
            container.innerHTML = html;
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // Search functionality
        function searchTables() {
            const searchTerm = document.getElementById('searchInput').value.toLowerCase().trim();
            const tables = document.querySelectorAll('.table-card');
            
            tables.forEach(table => {
                const tableName = table.querySelector('.table-card-title').textContent.toLowerCase();
                const tableContent = table.textContent.toLowerCase();
                
                if (searchTerm === '' || tableName.includes(searchTerm) || tableContent.includes(searchTerm)) {
                    table.style.display = 'block';
                } else {
                    table.style.display = 'none';
                }
            });
        }
        
        // Initialize on page load
        document.addEventListener('DOMContentLoaded', function() {
            // Restore active tab
            const savedTab = localStorage.getItem('activeTab') || 'erDiagramTab';
            const tabButton = document.querySelector(`[onclick*="${savedTab}"]`);
            if (tabButton) {
                tabButton.click();
            } else {
                // Default to first tab
                document.querySelector('.nav-tab').click();
            }
            
            // Load first table data by default in data tab
            const firstTable = document.querySelector('.table-name')?.textContent;
            if (firstTable) {
                loadTableData(firstTable);
            }
            
            // Add click handlers to table nodes
            document.querySelectorAll('.table-node').forEach(node => {
                node.addEventListener('click', function() {
                    const tableName = this.dataset.table;
                    selectTable(tableName);
                    showTab('dataTab');
                });
            });
            
            // Add keyboard shortcuts
            document.addEventListener('keydown', function(e) {
                // Ctrl/Cmd + F for search
                if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
                    e.preventDefault();
                    const searchTab = document.querySelector('[onclick*="schemaTab"]');
                    if (searchTab) {
                        searchTab.click();
                        document.getElementById('searchInput')?.focus();
                    }
                }
                
                // Escape to clear search
                if (e.key === 'Escape') {
                    const searchInput = document.getElementById('searchInput');
                    if (searchInput && document.activeElement === searchInput) {
                        searchInput.value = '';
                        searchTables();
                    }
                }
            });
        });
    </script>
    '''
    
    # Calculate statistics
    total_tables = len(tables)
    total_columns = sum(len(schema[table]['columns']) for table in tables)
    total_rows = sum(schema[table]['row_count'] for table in tables)
    total_relationships = len(relationships)
    
    # Generate statistics HTML
    stats_html = f'''
    <div class="header-stats">
        <div class="stat-item">
            <span class="stat-value">{total_tables}</span>
            <span class="stat-label">Tables</span>
        </div>
        <div class="stat-item">
            <span class="stat-value">{total_columns}</span>
            <span class="stat-label">Columns</span>
        </div>
        <div class="stat-item">
            <span class="stat-value">{total_rows}</span>
            <span class="stat-label">Rows</span>
        </div>
        <div class="stat-item">
            <span class="stat-value">{total_relationships}</span>
            <span class="stat-label">Relations</span>
        </div>
    </div>
    '''
    
    # Generate navigation tabs
    nav_tabs = '''
    <div class="nav-tabs">
        <button class="nav-tab active" onclick="showTab('erDiagramTab')">
            <i class="fas fa-project-diagram"></i> ER Diagram
        </button>
        <button class="nav-tab" onclick="showTab('schemaTab')">
            <i class="fas fa-table"></i> Schema
        </button>
        <button class="nav-tab" onclick="showTab('dataTab')">
            <i class="fas fa-database"></i> Data Viewer
        </button>
        <button class="nav-tab" onclick="showTab('relationshipsTab')">
            <i class="fas fa-link"></i> Relationships
        </button>
    </div>
    '''
    
    # Generate ER Diagram Tab
    er_diagram_tab = f'''
    <div id="erDiagramTab" class="tab-content active fade-in">
        <div class="er-diagram-container">
            {er_diagram}
        </div>
    </div>
    '''
    
    # Generate Schema Details Tab
    schema_tab = '''
    <div id="schemaTab" class="tab-content" style="display: none;">
        <div class="controls">
            <div class="control-group">
                <input type="text" id="searchInput" placeholder="Search tables and columns..." 
                       class="form-control" onkeyup="searchTables()"
                       style="flex-grow: 1; min-width: 250px;">
                <button class="btn" onclick="searchTables()">
                    <i class="fas fa-search"></i> Search
                </button>
                <button class="btn btn-secondary" onclick="document.getElementById('searchInput').value=''; searchTables();">
                    <i class="fas fa-times"></i> Clear
                </button>
            </div>
        </div>
        <div class="table-details-section">
    '''
    
    for table in tables:
        table_info = schema[table]
        columns = table_info['columns']
        fks = table_info['foreign_keys']
        
        schema_tab += f'''
        <div class="table-card">
            <div class="table-card-header">
                <div class="table-card-title">{table}</div>
                <div class="table-card-stats">
                    <span class="stat-badge rows">{table_info['row_count']}</span>
                    {f'<span class="stat-badge pk">{len([c for c in columns if c["pk"]])}</span>' if any(c['pk'] for c in columns) else ''}
                    {f'<span class="stat-badge fk">{len(fks)}</span>' if fks else ''}
                </div>
            </div>
            <div class="table-card-body">
                <table class="schema-table">
                    <thead>
                        <tr>
                            <th>Column</th>
                            <th>Type</th>
                            <th>Nullable</th>
                            <th>Key</th>
                        </tr>
                    </thead>
                    <tbody>
        '''
        
        for col in columns:
            key_badges = ''
            if col['pk']:
                key_badges += '<span class="key-badge pk-badge">PK</span>'
            
            is_fk = any(fk['from_column'] == col['name'] for fk in fks)
            if is_fk:
                key_badges += '<span class="key-badge fk-badge">FK</span>'
            
            nullable = 'NOT NULL' if col['not_null'] else '<span style="color: #6c757d;">NULL</span>'
            
            schema_tab += f'''
            <tr>
                <td><strong>{col['name']}</strong></td>
                <td><code>{col['type']}</code></td>
                <td>{nullable}</td>
                <td>{key_badges if key_badges else '-'}</td>
            </tr>
            '''
        
        schema_tab += '''
                    </tbody>
                </table>
            </div>
        </div>
        '''
    
    schema_tab += '</div></div>'
    
    # Generate Data Viewer Tab
    data_tab = f'''
    <div id="dataTab" class="tab-content" style="display: none;">
        <div class="data-viewer">
            <div class="controls">
                <div class="control-group">
                    <select id="selectedTable" onchange="loadTableData(this.value)" style="flex-grow: 1; min-width: 200px;">
                        <option value="">Select a table...</option>
                        {''.join(f'<option value="{table}">{table}</option>' for table in tables)}
                    </select>
                    <button class="btn" onclick="loadTableData(document.getElementById('selectedTable').value)">
                        <i class="fas fa-sync-alt"></i> Refresh
                    </button>
                </div>
            </div>
            <div id="dataTableContainer">
                <div class="empty-state">
                    <i class="fas fa-database"></i>
                    <h3>Select a table to view data</h3>
                    <p>Choose a table from the dropdown above to display its contents</p>
                </div>
            </div>
        </div>
    </div>
    '''
    
    # Generate Relationships Tab
    relationships_tab = '''
    <div id="relationshipsTab" class="tab-content" style="display: none;">
        <div class="data-viewer">
            <h3 style="margin-bottom: 16px; font-size: 1.2em;">Foreign Key Relationships</h3>
            <div class="data-table-container">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>From Table</th>
                            <th>From Column</th>
                            <th>To Table</th>
                            <th>To Column</th>
                            <th>Type</th>
                        </tr>
                    </thead>
                    <tbody>
    '''
    
    if relationships:
        for rel in relationships:
            relationships_tab += f'''
            <tr>
                <td><strong>{rel['from_table']}</strong></td>
                <td><code>{rel['from_column']}</code></td>
                <td><strong>{rel['to_table']}</strong></td>
                <td><code>{rel['to_column']}</code></td>
                <td><span style="color: #6c757d; font-size: 0.9em;">Foreign Key</span></td>
            </tr>
            '''
    else:
        relationships_tab += '''
            <tr>
                <td colspan="5" style="text-align: center; color: #6c757d; padding: 40px;">
                    No foreign key relationships defined in the database
                </td>
            </tr>
        '''
    
    relationships_tab += '''
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    '''
    
    # Full HTML
    html_content = f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Database Schema Viewer</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        {styles}
    </head>
    <body>
        <div class="container">
            <header class="main-header">
                <div class="header-title">
                    <h1><i class="fas fa-database"></i> Database Schema Viewer</h1>
                    <p>Interactive ER diagram and schema visualization</p>
                </div>
                {stats_html}
            </header>
            
            {nav_tabs}
            
            {er_diagram_tab}
            {schema_tab}
            {data_tab}
            {relationships_tab}
        </div>
        
        {scripts}
    </body>
    </html>
    '''
    
    return html_content

# ==============================================
# API ENDPOINTS
# ==============================================

@app.route('/api/db/schema')
def get_schema_api():
    """Get database schema as JSON"""
    try:
        schema, relationships, tables = get_table_schema()
        return jsonify({
            'tables': tables,
            'schema': schema,
            'relationships': relationships
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/db/stats')
def get_stats_api():
    """Get database statistics"""
    try:
        schema, relationships, tables = get_table_schema()
        
        total_columns = sum(len(schema[table]['columns']) for table in tables)
        total_rows = sum(schema[table]['row_count'] for table in tables)
        
        return jsonify({
            'total_tables': len(tables),
            'total_columns': total_columns,
            'total_rows': total_rows,
            'total_relationships': len(relationships),
            'tables': {table: schema[table]['row_count'] for table in tables}
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/db/table/<table_name>')
def get_table_data_api(table_name):
    """Get data from specific table"""
    try:
        data, columns = get_table_data(table_name, 100)
        return jsonify({
            'table': table_name,
            'columns': columns,
            'count': len(data),
            'data': data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/db/table/<table_name>/<int:limit>')
def get_table_data_limit_api(table_name, limit):
    """Get data from specific table with limit"""
    try:
        data, columns = get_table_data(table_name, limit)
        return jsonify({
            'table': table_name,
            'columns': columns,
            'count': len(data),
            'data': data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==============================================
# MAIN APPLICATION - ENHANCED HOME PAGE
# ==============================================

@app.route('/')
def index():
    """Enhanced home page - clean and compact"""
    try:
        # Get database stats for the homepage
        schema, relationships, tables = get_table_schema()
        total_tables = len(tables)
        total_rows = sum(schema[table]['row_count'] for table in tables)
    except:
        total_tables = 0
        total_rows = 0
    
    return f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Gateway Database Viewer</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }}
            
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
            }}
            
            .container {{
                background: rgba(255, 255, 255, 0.95);
                border-radius: 16px;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
                padding: 30px;
                max-width: 800px;
                width: 100%;
                text-align: center;
            }}
            
            .logo {{
                color: #3498db;
                font-size: 2.8em;
                margin-bottom: 15px;
            }}
            
            h1 {{
                color: #2c3e50;
                font-size: 1.8em;
                margin-bottom: 10px;
                font-weight: 600;
            }}
            
            .subtitle {{
                color: #7f8c8d;
                font-size: 1em;
                margin-bottom: 30px;
                line-height: 1.5;
            }}
            
            .stats {{
                display: flex;
                justify-content: center;
                gap: 20px;
                margin-bottom: 30px;
                flex-wrap: wrap;
            }}
            
            .stat-card {{
                background: #f8f9fa;
                padding: 15px;
                border-radius: 10px;
                min-width: 120px;
            }}
            
            .stat-value {{
                display: block;
                font-size: 1.6em;
                font-weight: bold;
                color: #3498db;
                margin-bottom: 5px;
            }}
            
            .stat-label {{
                color: #6c757d;
                font-size: 0.85em;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            
            .btn-group {{
                display: flex;
                flex-direction: column;
                gap: 12px;
                margin-bottom: 30px;
            }}
            
            .btn {{
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 10px;
                padding: 14px;
                background: #3498db;
                color: white;
                text-decoration: none;
                border-radius: 10px;
                font-weight: 600;
                transition: all 0.3s ease;
                border: none;
                cursor: pointer;
                font-size: 1em;
            }}
            
            .btn:hover {{
                background: #2980b9;
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(52, 152, 219, 0.3);
            }}
            
            .btn-primary {{
                background: #3498db;
            }}
            
            .btn-secondary {{
                background: #2c3e50;
            }}
            
            .btn-secondary:hover {{
                background: #1a252f;
            }}
            
            .features {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 15px;
                text-align: left;
            }}
            
            .feature {{
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                border-left: 3px solid #3498db;
            }}
            
            .feature-icon {{
                color: #3498db;
                font-size: 1.2em;
                margin-bottom: 8px;
            }}
            
            .feature h3 {{
                color: #2c3e50;
                font-size: 0.95em;
                margin-bottom: 5px;
            }}
            
            .feature p {{
                color: #6c757d;
                font-size: 0.85em;
                line-height: 1.4;
            }}
            
            .footer {{
                margin-top: 30px;
                color: #6c757d;
                font-size: 0.85em;
                border-top: 1px solid #dee2e6;
                padding-top: 15px;
            }}
            
            @media (max-width: 768px) {{
                .container {{
                    padding: 20px;
                }}
                
                .features {{
                    grid-template-columns: 1fr;
                }}
                
                .stats {{
                    gap: 10px;
                }}
                
                .stat-card {{
                    min-width: 100px;
                    padding: 12px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">
                <i class="fas fa-database"></i>
            </div>
            
            <h1>Gateway Database Viewer</h1>
            <p class="subtitle">
                Interactive visualization tool for exploring database schema, 
                relationships, and data with enhanced ER diagrams.
            </p>
            
            <div class="stats">
                <div class="stat-card">
                    <span class="stat-value">{total_tables}</span>
                    <span class="stat-label">Tables</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value">{total_rows}</span>
                    <span class="stat-label">Total Rows</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value"><i class="fas fa-check"></i></span>
                    <span class="stat-label">Connected</span>
                </div>
            </div>
            
            <div class="btn-group">
                <a href="/db" class="btn btn-primary">
                    <i class="fas fa-project-diagram"></i>
                    Launch Database Viewer
                </a>
                <a href="/api/db/schema" class="btn btn-secondary">
                    <i class="fas fa-code"></i>
                    View JSON Schema API
                </a>
            </div>
            
            <div class="features">
                <div class="feature">
                    <div class="feature-icon">
                        <i class="fas fa-project-diagram"></i>
                    </div>
                    <h3>Interactive ER Diagram</h3>
                    <p>Visualize relationships with clickable table nodes.</p>
                </div>
                <div class="feature">
                    <div class="feature-icon">
                        <i class="fas fa-table"></i>
                    </div>
                    <h3>Schema Explorer</h3>
                    <p>View tables, columns, data types, and constraints.</p>
                </div>
                <div class="feature">
                    <div class="feature-icon">
                        <i class="fas fa-database"></i>
                    </div>
                    <h3>Data Viewer</h3>
                    <p>Browse table data with JSON formatting.</p>
                </div>
                <div class="feature">
                    <div class="feature-icon">
                        <i class="fas fa-link"></i>
                    </div>
                    <h3>Relationships</h3>
                    <p>Analyze foreign key relationships.</p>
                </div>
            </div>
            
            <div class="footer">
                <p>© 2024 Gateway Database Viewer | Built with Flask & SQLite</p>
            </div>
        </div>
    </body>
    </html>
    '''

if __name__ == '__main__':
    # Initialize database if needed
    if init_database():
        print("\n" + "="*50)
        print("DATABASE VIEWER")
        print("="*50)
        print("\n✅ Database initialized successfully")
        print(f"\n🌐 Access Points:")
        print(f"   Home Page:       http://127.0.0.1:5000/")
        print(f"   Database Viewer: http://127.0.0.1:5000/db")
        
        print("\n📊 API Endpoints:")
        print("   GET /api/db/schema                - Complete schema")
        print("   GET /api/db/stats                 - Statistics")
        print("   GET /api/db/table/<table>         - Table data (100 rows)")
        print("   GET /api/db/table/<table>/<limit> - Custom limit")
        
        print("\n" + "="*50)
        print("Starting server...")
        print("="*50)
        
        app.run(debug=True, host='0.0.0.0', port=5000)
    else:
        print("❌ Database not found. Please run database.py first.")