"""Configuration library."""

# DONE(jmyounker): Rename JsonLayer to ObjLayer
# DONE(jmyounker): Rename InnerJsonLayer to InnerObjLayer
# DONE(jmyounker): Add InnerJsonLayer
# DONE(jmyounker): Add array indexing to JsonLayers
# DON(jmyounker): Add PropertyFileLayer
# DONE(jmyounker): Add Toml converter
# DONE(jmyounker): Add IniLayer
# DONE(jmyounker): Add Yaml converter
# DONE(jmyounker): Add AwsSecretsManagerLoader
# DONE(jmyounker): Add AwsParameterStoreFetcher
#   DONE(jmyounker): Create param tree facade
#   DONE(jmyounker): Create param tree walker
#   DONE(jmyounker): Accept expandable prefix
#   TODO(jmyounker): Test reload flushes removed params
#   TODO(jmyounker): Test reload finds added params
# DONE(jmyounker): Add non-blocking fetching
# TODO(jmyounker): Prototype logging system
# DONE(jmyounker): Test converters
# DONE(jmyounker): Unify loader operations into single context manager
# DONE(jmyounker): Consider getting rid of loader classes, and just using context managers.
#   -- Class still useful for various tricks, notably setting filenames for autodiscover.
#      Could do with a generic context response, but that seems like over-complication.
# DONE(jmyounker): Change loaders from io.Bytes to bytes
# DONE(jmyounker): Test loader expansions
# DONE(jmyounker): Test loader expansions
# DONE(jmyounker): Add path expansion to AwsSecretsManagerLoader
# DONE(jmyounker): Add is_enabled to AwsSecretsManagerLoader
# DONE(jmyounker): Split out requirements-dev.txt file
# DONE(jmyounker): Add fix for key expansion layer
# TODO(jmyounker): Layer builder creates context
# TODO(jmyounker): Add root layer to context
# DONE(jmyounker): Smart layer searches root or GetterLayer
# DONE(jmyounker): Create response mechanism
# DONE(jmyounker): Thread response mechanism through
# DONE(jmyounker): Wire in caching
# TODO(jmyounker): Improving names in Response class
# TODO(jmyounker): Improves names in cache classes
# DONE(jmyounker): Create caching getter
# DONE(jmyounker): Think about high-level UI
# TODO(jmyounker): Add sqlalchemy connector
# TODO(jmyounker): Add sops file layer
# DONE(jmyounker): Add from_key to extract values anywhere -- value(ctx, lower) interface
# DONE(jmyounker): Add generic parameter expansions for refreshes
# DONE(jmyounker): Add format based autodetection - decomposed into discrete tasks
# DONE(jmyounker): Improve TTL option names
# DONE(jmyounker): TTL option value expansions
# TODO(jmyounker): Test TTL option value expansions
# TODO(jmyounker): Add project root directory builder
# TODO(jmyounker): Add username builder
# DONE(jmyounker): Make filename a value() field in the file loader
# DONE(jmyounker): Define format types
# DONE(jmyounker): Define format-types to constructors table
# DONE(jmyounker): Define file types to format table
# DONE(jmyounker): Cache filename in file loader object
# DONE(jmyounker): Add smart constructor which uses filename in loader to choose correct constructor
# DONE(jmyounker): Move AWS loaders into aws package
# DONE(jmyounker): Create file builder
# DONE(jmyounker): Create AWS parameter store builder
# DONE(jmyounker): Value builder
# TODO(jmyounker): Create AWS secrets builder
# TODO(jmyounker): Clean up value() interface constructors
# TODO(jmyounker): Make aws property loader prefix into a value()
# DONE(jmyounker): Make aws secrets loader name a value()
# DONE(jmyounker): Add auto base64 decodes for AWS loaders
# TODO(jmyounker): Add envar only transform to builder.value
# TODO(jmyounker): Add do-not-fetch-value-from-config to builder.value so it can be used for things that must be envars or defaults
# TODO(jmyounker): Add required values
# TODO(jmyounker): Per-getter caching
# TODO(jmyounker): Allow parameterization of layer_constructor map
# TODO(jmyounker): Replace is_enabled with variable mechanism
# TODO(jmyounker): Improve names for vars and vars.compile
# TODO(jmyounker): Add auto-naming to layer construction
# TODO(jmyounker): Simplify smart layer construction in builder tests
# DONE(jmyounker): Fix damn circular imports
