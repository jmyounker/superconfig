
SuperConfig
=

SuperConfig provides a simple interface to configuration information sources.

A Config is a tree. Nodes and leaves are named. A Config has two operations:

```python
x = config["path"]
x = config.get("path", default=None)
```

The `"path"` specifies a location in the tree. The parts of the path are
separated by periods.


A Simple Config
==

Suppose that you have a json file that you want to use as a config. Let's call
it `/tmp/base-config.json`.

This file contains:
```json
{
  "a": {
    "b": 1,
    "c": 2
  }
}
```

To use this you would create the following config:


```python
from superconfig import builders as bld

config = bld.config_stack(
    bld.file_layer("/tmp/base-config.json"), 
)
```

Using the config is straight-forward:

```python
>>> config["a.b"]
1
>>> config["a.c"]
2
>>>
```

Accessing a non-existent path raises a KeyError:

```python
>>> c["g"]
Traceback (most recent call last):
File "<stdin>", line 1, in <module>
File "/Users/jeffyounker/repos/superconfig/superconfig/config.py", line 126, in __getitem__
raise KeyError("key {} not found".format(key))
KeyError: 'key g not found'
>>>
```

A Simple Config with Overrides
==
A frequent configuration pattern is a master config file with local overrides. Let's call
these `/etc/base-config.json` and `./overrides.json`. You could specify this as:

```python
from superconfig import builders as bld

config = bld.config_stack(
    bld.file_layer("./overrides.json"),
    bld.file_layer("/tmp/base-config.json"), 
)
```
If `/tmp/base-config.json` has the same contents as the previous example, and if the
override the file contains:

```json
{
  "a": {
    "b": 3
  }
}
```

Then instead of `config["a.b"]` returning `1`, it returns `3`. The call `config["a.c"]`
stills returns `2` because the override does not define the key `"a.c"`.

In general, superconfig starts with the top layer in your config stack, and it searches
from the top layer down to the bottom layer, and it returns the first match that it finds.

Using Config Files In Your Home Directory
==
Frequently you'll want to put config files in your home directory. This config gets the
overrides file from your home directory:

```python
from superconfig import builders as bld


config = bld.config_stack(
    bld.file_layer("{{home}}/overrides.json"),
    bld.file_layer("/tmp/base-config.json"),
    {
        "home": bld.homedir(),
    }
)

```

The first thing to notice is the `{{home}}` expansion in the top layer. At runtime
this is expanded to key `home`'s value.

The expansion process starts at the next layer below, and it searches each layer below
for the key `home`. Thew new bottom layer defines a special handler for the `home` key.
This handler finds the home directory path using the Python library function
`pathlib.Path.home()`.

Important Concepts
==

In order to make best use of this library, you should be familiar with two concepts:

 * Layers
 * Getters

Layers
==
A config consists of layers. Layers are searched from top to bottom. The first
match found is the first returned.  There are multiple kinds of layers, performing
a variety of jobs. Tasks include:

* Load config trees from files.
* Load config trees from external stores like AWS config manager.
* Cache results from expensive lookups.
* Load a config tree an encrypted datastore.

There is a special kind of layer called a Getter Layer. The keys in this kind of
layer attach to handlers. These handlers accept perform actions to retrieve
values. These handlers are called Getters.

Getters
==

There are a variety of getters. Getters find either return a value for a key or report
that nothing was found. You've already seen one kind of getter, the `misc.HomeDirGetter`,
returned by `bld.homedir()`. Things that getters can do include:

* Get a value from an envionment variable.
* Look up a secret in an external datastore.
* Cache a result.
* Perform a transformation on a value from another getter.
* Look up a result in a lower layer.
* Attach a layer as a subtree.
* Stack getters one on top of another.
* Map one value one key to another.
* Perform a computation.
* Connect to a database.


