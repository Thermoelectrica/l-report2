"""Reserved (engine-injected) SQL parameters.

These are never taken from the client: the engine sets them server-side and
strips any client-supplied value with the same name. Report metadata must not
declare parameters with these names.

- ``current_inspector_id`` (integer): logged-in inspector, JWT ``sub``. NULL if
  the user is not authenticated.
- ``plant_ids`` (uuid[]): plants the report may read. Set only from the value
  returned by the report's ``access_query``; absent if there is none.
"""

CURRENT_INSPECTOR_PARAM = "current_inspector_id"
PLANT_IDS_PARAM = "plant_ids"

# Postgres cast appended to the positional placeholder of each reserved param
RESERVED_PARAM_CASTS = {
    CURRENT_INSPECTOR_PARAM: "::integer",
    PLANT_IDS_PARAM: "::uuid[]",
}

RESERVED_PARAMS = frozenset(RESERVED_PARAM_CASTS)
