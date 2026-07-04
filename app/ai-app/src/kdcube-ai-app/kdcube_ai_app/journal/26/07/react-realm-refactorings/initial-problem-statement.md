# Problems: 

## Move the previously 'top' level namespaces of react-like artifacts  to the 'conv' namespace
1) moving the fi:, ar:, su:, so: uris that correspond to uris of the artifacts in the "react harness world" to conv: so become conv:fi:, conv:ar:, etc. becuase this way its clear that they belong to conv: namespace which represents these artifacts properly as belong to "conversation" realm /Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/docs/sdk/solutions/conversation/as-named-service-provider-README.md


/Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/docs/sdk/namespace-services/clients-README.md
/Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/docs/sdk/namespace-services/discovery-README.md
/Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/docs/sdk/namespace-services/integration-README.md
/Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/docs/sdk/namespace-services/object-ref-presentation-and-actions-README.md
/Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/docs/sdk/namespace-services/ontologic-tools-README.md
/Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/docs/sdk/namespace-services/providers-README.md
/Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/docs/sdk/namespace-services/react-object-materialization-README.md
/Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/docs/sdk/namespace-services/react-object-policy-bridge-README.md
/Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/docs/sdk/namespace-services/README.md

and make natural serving of the artifacts that happen in this realm in the conversation service   /Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/conversation/named_service.py. The problem now that react agent manipulates these uris according to its instructions
/Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/skills/instructions/shared_instructions.py
/Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/skills/instructions/shared_instructions_lite.py
and i believe also this is stated in some tools docs (at least in reactive docs for sure)
/Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/react/tools/read.py
/Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/react/tools/rg.py
/Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/react/tools/write.py
/Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/react/tools/pull.py
/Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/react/tools/plan.py
/Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/react/tools/patch.py
/Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/react/tools/memsearch.py
/Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/react/tools/hide.py
/Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/react/tools/external.py
/Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/react/tools/common.py
/Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/react/tools/checkout.py
/Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/react/tools/__init__.py

And that entire react harness depends on resolving and handling these fi: , so:, su: , ar:, tc:, sk:, ws:   
But in our system all is named services, and there are other named services. and the artifact that belongs to some service must be prfixed with that service prefix.
This made available exposing the stable set of tools (about/schema/search/upsert/get/etc.) for agents "on top of" all configured/known named services.
For example, now i have the bundle kdcube service that serves mcp around these services.
/Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/bundles/kdcube-services@1-0/entrypoint.py

The problem is that if we connect the agent to such services, and it rerieves the conversations using memsearch or get, these conversations contain artufacts in fi: and so: format, ar: format.
And additionally this is what stated in turn summaries that react is enocuraged to egnerate at teh end of turn (to include uris of artifcats it worked with in this turn).
while we cannot publish the fi:, ar: services becuase they simply do not exist. Hence we need to move them hard to conv: so they always stated like this in bot react summaries, in the conversations fetched by named_services.get(ns="conv", ..). And this is the problem number 1.

Note also that sk: correspond to skill resolution system so it should be synchronzied with it.
And so: is related to sources pool system so also must be synchronized.

## Wrong names of the folders inside the react workspace.
   Look in react instructions /Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/skills/instructions/shared_instructions.py:

1) CURRENT TURN WORKSPACE (physical; current-turn execution surface; STARTS EMPTY EACH TURN)
   OUTPUT_DIR/
   turn_<current>/                    # git working tree — repo root for THIS turn (always git mode)
   files/<workspace_scope>/...      # durable project state — COMMITTED to git each turn (versioned; pull/checkout next turn)
   outputs/<artifact_scope>/...     # produced artifacts — NOT git-tracked; survive only if listed in the exec contract (hosting)
   snapshots/...                    # story/wizard state — also git-committed
   attachments/...                  # current user uploads; already turn-scoped (not git-tracked)
   external/...                     # rehosted event/domain attachments or evidence (not git-tracked)
   .git/                            # versions files/ and snapshots/ ONLY — outputs/attachments/external are NOT committed
   logs/
   timeline.json
   ...

what is called "files" had to be "git/projects" (because its for continuous projects)
whats is called "outputs" had to be "files" (because its individual files)
what is called "snapshots" had to be called "git/snapshots" because we also store snapshots under git.
This way this absolutely correspond the proper model of how the data stored and how react must build the paths. this makes this absolutely clear model.
we recently already tried to "smooth" the sharp effect of this wrong naming. because of the wrong naming its harder for teh agent to decide what it should put where. this "outptus" is very confusing. and the fact that although we store the snaphosts and the "files" under git they somehow not even under "git".
So weird, very weird.
Files is more suitable naming for individual files however now that thing is called "outputs".
So this is the second thing that absolutely must be replaced asap now before we started to make the traction and people start to maintain conversations and grow the data in these conversartions.
Becuase if we refactor these names, this will influence how the artifacts are stored in the hosting /Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/react/solution_workspace.py /Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/runtime/workspace.py /Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/runtime/workdir_discovery.py  /Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/storage/conversation_store.py
This also require a lot of changes and very attentive reading of each tool doc including /Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/tools/exec_tools.py and other tools in this folder, and also reactive tools, and entire react harness /Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/react/v2/runtime.py
/Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/react/v3/runtime.py
and probably in many other places..

But this must be desoite the pain reworked. And it must be reworked now because all artifacts that were made previosly will stop work after these changes.

Also all existing documentaion on react /Users/elenaviter/src/kdcube/kdcube-ai-app/app/ai-app/docs/sdk/agents/react must be aligned after this change is introduced. 

