# Ollama Testing

I have a local ollama server and figured this might be a good time to test some local models and how they fare with actual development coding.

## TL;DR

We ain't there yet. They all sucked and they're all hella slow compared to the Claude's and GPTs. All disappointing despite all the hype. 
You're better off bang:buck to just get the [Github Copilot $10/mo](https://github.com/features/copilot/plans) and not a $500 GPU as I did (you get vastly better LLM for $120/yr). So in a year or two, that same $500 will buy a better card with more RAM and faster GPUs for sure. I'll never recoup my money at this rate.

It's honestly really disapointing TBH. I didn't expect "Claude" but I did expect "something". I feel lied to.

"Local LLM" should stand for "Lies Lies Lies and More lies"

## The prompt

I basically used the same prompt for all of them; especially since not one of them did a damn thing!

I already have the Vobot ntfy code. I figured this is a simple task I don't have to waste my subscription on and can leverage local LLM "perfectly" for. 

I created some pngs and put them in the resources folder, appropriatly named even. We already show a "NEW" text message. I mean this really couldn't get much simpler; I could probably wire it in myself at this point.

I simply asked, "Can we use the priority png icons for when a new ntfy message comes in instead of the "NEW" text?"

## nVidia RTX 5060 Ti 16 GB VRAM

I used `nvtop` and `nvidia-smi` to view what the GPU was doing as well.

I used `ollama ps` to ensure the model was loaded (which chat automatically does)

## Models Pulled
```
root@ollama:~# ollama ls

NAME                          ID              SIZE      MODIFIED
gemma3:12b                    f4031aab637d    8.1 GB    6 seconds ago
devstral-small-2:24b          24277f07f62d    15 GB     6 seconds ago
gpt-oss:latest                17052f91a42e    13 GB     7 seconds ago
qwen3:14b                     bdbd181c33f2    9.3 GB    7 seconds ago
llama3.2:latest               a80c4f17acd5    2.0 GB    6 seconds ago
phi4-mini-reasoning:latest    3ca8c2865ce9    3.2 GB    8 seconds ago
qwen2.5-coder:14b             9ec8897f747e    9.0 GB    8 seconds ago
llama3.1:8b                   46e0c10c039e    4.9 GB    8 seconds ago
qwen3:latest                  500a1f067a9f    5.2 GB    9 seconds ago
qwen3-coder:30b-a3b-q4_K_M    06c1097efce0    18 GB     9 seconds ago
ministral-3:14b               4760c35aeb9d    9.1 GB    10 seconds ago
mistral:latest                6577803aa9a0    4.4 GB    9 seconds ago
phi4-mini:latest              78fad5d182a7    2.5 GB    10 seconds ago
```

## devstral-small-2:24b

First one I tried was `devstral-small-2:24b` which is supposed to be the new hotness.

It was an exercise in frustration where I'd ask it to do something, it seemed to understand but then did nothing. I'd ask again, same recursive loop.

It would spit out code the the chat and then ask me what did I want to do. I'd ask it to edit the files and it'd forget what we were doing (context)! UGH!

[specstory here](.specstory\history\2025-12-15_23-04Z-using-png-icons-for-ntfy-message-notifications.md)

## qwen2.5-coder:14b

Next I tried what was also supposed to be a champ and community favorite but that was even worse.
I couldn't get it do do anything but "error" with this over and over

```json
{
"name": "replace_string_in_file",
"arguments": {
        "filePath": "d:\daevid\Code\Vobot\ntfy\apps\ntfy\init.py",
        "oldString": ""NEW"",
        "newString": "# Use priority icon instead of 'NEW' text"
    }
}
```

[specstory here](.specstory\history\2025-12-15_23-34Z-using-icons-for-ntfy-message-notifications.md)

## gpt-oss:latest

This one seemed like it was going to do something interesting, and it was noticably faster compared to the other two.

Then it just kind of stopped working all together. "Sorry, no response was returned" messages and things like that in Chat. Despite moments before it literally showed a bunch of code for a Vobot app. Unfortunately it was a "fresh" skeleton app and not MY app (it literally has in the VSCode editor tab)

At one point the GPU sounded like a jet engine and sustained the fans and 83% GPU for MINUTES. I was expecting "something" from that "Working..." prompt. Nothing but the same old "Sorry, no reponse was returned". Womp womp...

## llama3.2:latest

Also surprisingly fast (it's only a 2.8 GB model though). But shockingly it did return some code that seemed legit. It didn't edit my code however even when asking it to. It would just spit the code to the chat window like the before times.

## qwen3:latest

It seemed to be hung on some previous prompt about an MCP pylance tool or something. I did a `/clear` and re-attached the markdown files. 

Surprisingly it generated some code and said it would resize and rename the images. So far so good.

It ended wth "Would you like me to implement the actual icon handling logic and update the file?" ... not ideal but better safe than sorry I guess.

Then, the dumpster lit itself on fire when I simply confirmed with "yes please". 

```
The user's request "yes please" is too vague to determine a specific action. Could you please clarify what you'd like to do? For example:

 * Are you confirming a previous action?
 * Do you need help with a specific task related to the repository or file?
 * Would you like to create/update an issue in GitHub?
*  Do you need assistance with editing files or working with the repository?

Let me know how I can assist!
```

## qwen3-coder:30b-a3b-q4_K_M

This didn't do anything. Failed over and over.

```
Sorry, your request failed. Please try again.
Copilot Request id: cc028da9-d512-4bfd-b1ec-f6813cc5060d
Reason: stackTrace.format
```

I tried to run it manually and see I don't have enough ram? I was told I COULD run this model with my card. Bummer.

```
root@ollama:~# ollama run  qwen3-coder:30b-a3b-q4_K_M
Error: 500 Internal Server Error: model requires more system memory (3.0 GiB) than is available (1.5 GiB)
```