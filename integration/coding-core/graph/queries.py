"""
Pre-built Cypher queries for the 7-step agent inference chain.
Each query maps to one exploration step from CC-004 research.
"""

# Step 1: Entry Points — "Where does this thing start?"
FIND_ENTRY_POINTS = """
    MATCH (r:Route)-[:HANDLED_BY]->(m)
    OPTIONAL MATCH (m)<-[:CONTAINS_METHOD]-(c:Class)
    RETURN r.path AS route,
           r.http_method AS method,
           r.transport AS transport,
           m.name AS handler,
           c.name AS handler_class,
           m.file_path AS file
    ORDER BY r.path
"""

# Step 2: Architecture — handled inline in server.py (show_architecture tool)

# Step 3: Call Chain Trace — "What happens when X occurs?"
CALL_CHAIN_TRACE = """
    MATCH path = (entry)-[:CALLS*1..5]->(leaf)
    WHERE entry.qualified_name = $qname
    WITH path, [n in nodes(path) | n.qualified_name] AS chain
    RETURN chain, length(path) AS depth
    ORDER BY depth
    LIMIT 50
"""

# Step 4: Find References — "Who uses this?"
FIND_REFERENCES = """
    MATCH (target {qualified_name: $qname})
    OPTIONAL MATCH (caller)-[:CALLS]->(target)
    OPTIONAL MATCH (child:Class)-[:INHERITS]->(target)
    OPTIONAL MATCH (impl:Class)-[:IMPLEMENTS]->(target)
    OPTIONAL MATCH (override:Method)-[:OVERRIDES]->(target)
    OPTIONAL MATCH (ref)-[:REFERENCES]->(target)
    OPTIONAL MATCH (test:Test)-[:TESTS]->(target)
    RETURN target.name AS name,
           target.qualified_name AS qualified_name,
           collect(DISTINCT caller.qualified_name) AS callers,
           collect(DISTINCT child.qualified_name) AS subclasses,
           collect(DISTINCT impl.qualified_name) AS implementors,
           collect(DISTINCT override.qualified_name) AS overrides,
           collect(DISTINCT ref.qualified_name) AS references,
           collect(DISTINCT test.name) AS tests
"""

# Step 5: Find Siblings — "What else works like this?"
FIND_SIBLINGS = """
    MATCH (target:Class)
    WHERE target.name = $name OR target.qualified_name = $name
    MATCH (target)-[:INHERITS]->(base:Class)<-[:INHERITS]-(sibling:Class)
    WHERE sibling.qualified_name <> target.qualified_name
    RETURN base.name AS parent,
           base.qualified_name AS parent_qname,
           collect(DISTINCT {
               name: sibling.name,
               qualified_name: sibling.qualified_name
           }) AS siblings
"""

# Step 6: Show Contract — "What's the interface?"
SHOW_CONTRACT = """
    MATCH (c:Class {qualified_name: $qname})
    OPTIONAL MATCH (c)-[:IMPLEMENTS]->(iface)
    OPTIONAL MATCH (iface)-[:CONTAINS_METHOD]->(im:Method)
    OPTIONAL MATCH (c)-[:INHERITS]->(parent:Class)
    OPTIONAL MATCH (parent)-[:CONTAINS_METHOD]->(pm:Method {is_abstract: true})
    WITH c, iface,
         collect(DISTINCT {name: im.name, signature: im.signature, is_abstract: im.is_abstract}) AS interface_methods,
         collect(DISTINCT {name: pm.name, signature: pm.signature}) AS abstract_parent_methods
    RETURN c.name AS class_name,
           c.qualified_name AS qualified_name,
           iface.name AS interface,
           iface.qualified_name AS interface_qname,
           interface_methods,
           abstract_parent_methods
"""

# Composite: Class Footprint — all steps combined
CLASS_FOOTPRINT = """
    MATCH (c:Class {qualified_name: $qname})

    OPTIONAL MATCH (c)-[:INHERITS*]->(ancestor:Class)
    OPTIONAL MATCH (descendant:Class)-[:INHERITS*]->(c)
    OPTIONAL MATCH (c)-[:IMPLEMENTS]->(iface:Interface)

    OPTIONAL MATCH (c)-[:CONTAINS_METHOD]->(m:Method)
    OPTIONAL MATCH (c)-[:CONTAINS_PROPERTY]->(p:Property)

    OPTIONAL MATCH (caller:Method)-[:CALLS]->(m)
    OPTIONAL MATCH (m)-[:CALLS]->(callee)

    OPTIONAL MATCH (c)-[:DOCUMENTED_BY]->(doc:DocSection)
    OPTIONAL MATCH (t:Test)-[:TESTS]->(c)
    OPTIONAL MATCH (c)-[:DECORATED_BY]->(dec:Decorator)

    RETURN c.name AS name,
           c.qualified_name AS qualified_name,
           c.file_path AS file_path,
           c.docstring AS docstring,
           c.is_abstract AS is_abstract,
           c.is_protocol AS is_protocol,
           collect(DISTINCT ancestor.qualified_name) AS ancestors,
           collect(DISTINCT descendant.qualified_name) AS descendants,
           collect(DISTINCT iface.qualified_name) AS interfaces,
           collect(DISTINCT {name: m.name, signature: m.signature, is_abstract: m.is_abstract, is_async: m.is_async}) AS methods,
           collect(DISTINCT {name: p.name, type: p.type_annotation}) AS properties,
           collect(DISTINCT caller.qualified_name) AS callers,
           collect(DISTINCT callee.qualified_name) AS callees,
           collect(DISTINCT {title: doc.title, file: doc.file_path}) AS docs,
           collect(DISTINCT t.name) AS tests,
           collect(DISTINCT dec.name) AS decorators
"""

# Semantic links for a class — concepts it embodies and policies governing it
CLASS_SEMANTIC_LINKS = """
    MATCH (c {qualified_name: $qname})
    WHERE c:Class OR c:Method OR c:Function OR c:Module OR c:Package
    OPTIONAL MATCH (c)-[:EMBODIES]->(concept:Semantic)
    WHERE concept IS NULL OR concept.kind = 'concept'
    WITH c, collect(DISTINCT {
        id: concept.id,
        scope: concept.scope,
        name: concept.name,
        category: concept.category,
        summary: concept.summary,
        aliases: concept.aliases
    }) AS raw_concepts
    OPTIONAL MATCH (c)-[:GOVERNED_BY]->(policy:Semantic)
    WHERE policy IS NULL OR policy.kind = 'policy'
    WITH raw_concepts, collect(DISTINCT {
        id: policy.id,
        scope: policy.scope,
        name: policy.name,
        category: policy.category,
        summary: policy.summary,
        rationale: policy.rationale,
        how_to_apply: policy.how_to_apply
    }) AS raw_policies
    RETURN [x IN raw_concepts WHERE x.id IS NOT NULL] AS concepts,
           [x IN raw_policies WHERE x.id IS NOT NULL] AS style_policies
"""


# Define a single Semantic node by name or alias (case-insensitive).
# `realized_by` is concept→code (EMBODIED_BY).
# `applied_to`  is policy→code (inverse of GOVERNED_BY) — classes governed by a policy.
DEFINE_SEMANTIC = """
    MATCH (s:Semantic)
    WHERE ($scope IS NULL OR s.scope = $scope)
      AND (
            toLower(s.name) = toLower($term)
         OR toLower(s.id)   = toLower($term)
         OR any(a IN s.aliases WHERE toLower(a) = toLower($term))
      )
    OPTIONAL MATCH (s)-[:RELATED_TO]-(rel:Semantic)
    OPTIONAL MATCH (s)-[:EMBODIED_BY]->(rb)
    WHERE rb:Class OR rb:Method OR rb:Function OR rb:Module OR rb:Package
    OPTIONAL MATCH (gov)-[:GOVERNED_BY]->(s)
    WHERE gov:Class OR gov:Method OR gov:Function OR gov:Module OR gov:Package
    RETURN s.id AS id,
           s.kind AS kind,
           s.scope AS scope,
           s.name AS name,
           s.aliases AS aliases,
           s.category AS category,
           s.summary AS summary,
           s.definition AS definition,
           s.rationale AS rationale,
           s.how_to_apply AS how_to_apply,
           s.pitfalls AS pitfalls,
           collect(DISTINCT {id: rel.id, scope: rel.scope, name: rel.name, kind: rel.kind}) AS related,
           collect(DISTINCT rb.qualified_name) AS realized_by,
           collect(DISTINCT gov.qualified_name) AS applied_to
    LIMIT 5
"""


# Impact Analysis — what breaks if this changes?
IMPACT_ANALYSIS = """
    MATCH (target {qualified_name: $qname})
    OPTIONAL MATCH (caller)-[:CALLS]->(target)
    OPTIONAL MATCH (child:Class)-[:INHERITS]->(target)
    OPTIONAL MATCH (override:Method)-[:OVERRIDES]->(target)
    OPTIONAL MATCH (test:Test)-[:TESTS]->(target)
    RETURN target.name AS name,
           target.qualified_name AS qualified_name,
           collect(DISTINCT caller.qualified_name) AS callers,
           collect(DISTINCT child.qualified_name) AS subclasses,
           collect(DISTINCT override.qualified_name) AS overrides,
           collect(DISTINCT test.name) AS tests
"""
