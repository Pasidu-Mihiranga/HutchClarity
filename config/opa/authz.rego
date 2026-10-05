package clarity.authz

import rego.v1

default allow := false

# Effective permissions for one role: (baseline ∪ attached) − detached (ADR-0045).
effective_perms(role) := perms if {
	baseline := {p | some p in object.get(data.clarity.role_permissions, role, [])}
	attached := {p | some p in object.get(input.role_attached, role, [])}
	detached := {p | some p in object.get(input.role_detached, role, [])}
	perms := (baseline | attached) - detached
}

role_grants(permission) if {
	some role in input.roles
	permission in effective_perms(role)
}

has_admin_role if {
	some role in input.roles
	role in data.clarity.admin_roles
}

admin_money_denied if {
	has_admin_role
	input.permission in data.clarity.money_permissions
}

# Separation of duties: whoever holds an audit duty cannot move money
# (audit assurance plan 5.6, rule 1). Mirrors ``permissions_for`` in Python.
holds_audit_duty if {
	some role in input.roles
	some duty in effective_perms(role)
	duty in data.clarity.audit_duty_permissions
}

holds_audit_duty if {
	some duty in input.granted
	duty in data.clarity.audit_duty_permissions
}

audit_duty_money_denied if {
	holds_audit_duty
	input.permission in data.clarity.money_permissions
}

step_up_missing if {
	input.permission in data.clarity.step_up_permissions
	input.assurance != "mfa-recent"
}

allow if {
	role_grants(input.permission)
	not admin_money_denied
	not audit_duty_money_denied
	not step_up_missing
}
