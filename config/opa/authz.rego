package clarity.authz

import rego.v1

default allow := false

role_grants(permission) if {
    some role in input.roles
    permission in data.clarity.role_permissions[role]
}

has_admin_role if {
    some role in input.roles
    role in data.clarity.admin_roles
}

admin_money_denied if {
    has_admin_role
    input.permission in data.clarity.money_permissions
}

step_up_missing if {
    input.permission in data.clarity.step_up_permissions
    input.assurance != "mfa-recent"
}

allow if {
    role_grants(input.permission)
    not admin_money_denied
    not step_up_missing
}
