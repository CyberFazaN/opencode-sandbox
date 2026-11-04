# Sourced by interactive Bash only, once per shell; no credentials are read here.
case $- in
    *i*)
        if [ "${OCS_PROVIDER_LOADED:-}" != 1 ] && [ -r /run/secrets/ocs-provider.json ]; then
            printf '%s\n' 'Provider profile is not loaded here: use ocs-opencode (private server); plain opencode does not load it.'
        fi
        ;;
esac
