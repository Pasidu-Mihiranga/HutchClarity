package clarity.authz_test

import data.clarity.authz

# Run with: opa test deploy/opa/ -v
# (safe as text even when the opa binary is not installed)

test_health_allowed_anonymous if {
	authz.allow with input as {"action": "health.read", "roles": []}
}

test_case_read_denied_without_staff if {
	not authz.allow with input as {"action": "case.read", "roles": ["customer"]}
}

test_case_read_allowed_for_staff if {
	authz.allow with input as {"action": "case.read", "roles": ["staff"]}
}

test_action_execute_allowed_for_supervisor if {
	authz.allow with input as {"action": "action.execute", "roles": ["supervisor"]}
}

test_admin_allows_anything if {
	authz.allow with input as {"action": "any.thing", "roles": ["admin"]}
}

test_default_deny if {
	not authz.allow with input as {"action": "secret.wipe", "roles": []}
}
