# Gerrit2Trac

Gerrit2Trac is a utility for updating Trac tickets via Gerrit Code Review hooks.

## Requirements

* Python >= 2.6.x
* [Gerrit](http://code.google.com/p/gerrit/) >= 2.7.x
* [Trac](http://trac.edgewall.org) >= 0.12.x
* [Trac XML-RPC Plugin](http://trac-hacks.org/wiki/XmlRpcPlugin)

## Assumptions

* A working knowledge of \*nix, Gerrit, Trac and Git.
* Gerrit's $site\_path is _/opt/gerrit2_.
* Login name (or UID) the Gerrit JVM executes as is _gerrit2_.
* _gerrit2_ is a valid Trac user with TICKET\_MODIFY privileges.
* Gerrit allows _Anonymous Users_ read access to _refs/*_.

## Configuration

Clone the Gerrit2Trac repository.

    git clone https://github.com/thefoxbox/gerrit2-trac.git

Copy the included sample configuration to your $site\_path/etc directory and protect the file contents.

    sudo cp ./gerrit2-trac/examples/gerrit2trac.config.sample /opt/gerrit2/etc/gerrit2trac.config
    sudo chown gerrit2:gerrit2 /opt/gerrit2/etc/gerrit2trac.config
    sudo chmod 0600 /opt/gerrit2/etc/gerrit2trac.config

Modify the configuration file _/opt/gerrit2/etc/gerrit2trac.config_, specifying the correct username, password and URLs for your site.

Copy the `gerrit2trac.py` script to your $site\_path/bin directory.

    sudo cp ./gerrit2-trac/gerrit2trac.py /opt/gerrit2/bin

Create the desired Gerrit hooks in your $site\_path/hooks directory.

    if [ ! -d /opt/gerrit2/hooks ]; then
        sudo mkdir /opt/gerrit2/hooks
    fi

    for hook in patchset-created reviewer-added comment-added change-merged; do
        if [ ! -e /opt/gerrit2/hooks/${hook} ]; then
            sudo cp ./gerrit2-trac/examples/patchset-created.sample /opt/gerrit2/hooks/${hook}
            sudo chmod 0755 /opt/gerrit2/hooks/${hook}
        fi
    done

If hooks already exist and you would still like to use Gerrit2Trac for updating tickets, you can add the following line to your hook:

    python /opt/gerrit2/bin/gerrit2trac.py $(basename $0) "$@"

## Usage

Once the Gerrit hooks have been created, any corresponding Gerrit action will update the Trac ticket referenced in the Git commit message.

## Workflow customization

Trac ticket update attributes _comment_, _action_ and _cc_  can be customized in the _[workflow]_ section of $site\_path/etc/gerrit2trac.config.
See the following examples for a sample custom workflow.

Variable substitution in comments is supported where _$variable_ is an available parameter.
See `gerrit2trac.py -h` for a list of available parameters.

See the Gerrit Hook [documentation](https://gerrit-review.googlesource.com/Documentation/config-hooks.html) for a list of
available hooks and the associated parameters.

Note: When using variable substitution, hyphenated parameters must be referenced without the hyphen.

## Examples

### Example Git commit message:

    This is an example Git commit message.

    Including a line with 'Ticket: #' will update an existing Trac ticket
    with pre-configured defaults or customized ticket actions.

    Customized ticket actions can be confgured in the [workflow] section
    of gerrit2trac.config.

    Ticket: 101
    Change-Id: I3ab5940714c59d81ed14fa22df1d5e506cd20cdd

### Example custom workflow:

    [workflow]
    ;
    ; An example patchset-created triggerd workflow
    ;
    ; * Adds a custom Gerrit comment using variable substitution and wiki formatting.
    ; * Adds the patch-set uploader to the ticket Cc: field.
    ;
    ; Note: remove the hyphen from hyphenated parameters.
    ;
    ; See ./gerrit2-trac/examples/gerrit2trac.config.sample for more examples.
    ;
    patchset_created.comment = A new patch-set is awaiting review.
        * Change-Id: $change
        * Change-Url: $changeurl
        * Patch-Set: $patchset
        * Uploader: $uploader
    patchset_created.action = leave
    patchset_created.cc = $uploader

