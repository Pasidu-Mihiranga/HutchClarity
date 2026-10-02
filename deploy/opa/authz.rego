package clarity.authz

# Deny by default. Composition root / API attaches input:
#   input.subject  (principal id)
#   input.roles    (list of role strings)
#   input.action   (permission string, e.g. "case.read")
#   input.resource (optional resource type)

default allow := false

allow if {
	input.action == "health.read"
}

allow if {
	"staff" in input.roles
	startswith(input.action, "case.")
}

allow if {
	"supervisor" in input.roles
	startswith(input.action, "action.")
}

allow if {
	"admin" in input.roles
}
