# Taste Concierge

Tell it what you love. It works out what to ask Qloo, and comes back with food, places,
music and film that connect to your taste.

**Live: https://qloo-hackathon.streamlit.app/**

Built for the Qloo Agentic Hackathon.

---

## The thing that convinced me this was worth building

Give Qloo one artist and ask it for bars.

```
John Coltrane  ->  New York:  Zinc Bar, Barbes, Smalls Jazz Club, The Bitter End
John Coltrane  ->  London:    Ronnie Scott's, the 100 Club, Troubadour, Ain't Nothin' But
```

Those are the jazz rooms of both cities. Now the same query with a different artist:

```
Calvin Harris  ->  New York:  230 Fifth Rooftop, Igloo Bar, Bar SixtyFive
Calvin Harris  ->  London:    Sky Garden, Empire Casino, Eighteen Sky Bar
```

Zero overlap between the two lists, in either city. Nobody typed "jazz". A language model
guessing from memory can name Ronnie Scott's, but it cannot tell you that *your* taste maps
there rather than somewhere else, and it has no way to show its working. Qloo's graph can.

## What it does

You write a sentence about what you like and who you're going out with. A Gemini agent is
handed four Qloo operations and decides for itself which to use:

| Tool | What it does |
|---|---|
| `resolve_taste` | a name you gave it becomes a Qloo entity id |
| `find_tag` | a cuisine or a genre becomes a Qloo tag id |
| `places` | restaurants, bars, cafes or live music in a city, shaped by that taste |
| `culture` | artists, films or books connected to it |

Then it writes up what came back. The app shows every call it made.

### What it deliberately does not do

It won't build you an itinerary. Qloo has no idea about opening hours, travel time, or what
order to do things in, so a timetable would be the language model inventing structure on top
of real data. That is the one part of the output that would not be grounded in anything, so
there isn't one.

## It actually decides things

"Agentic" is easy to claim, so there's a test that can fail:

```
python scripts/gate_check.py
```

It runs four different requests and compares the calls each one produced. If they all come
out the same, it prints FAIL, because that would be a fixed pipeline with a model narrating.

Last run:

| Request | Calls the model chose |
|---|---|
| qawwali and Kashmiri food, friends, Delhi | `find_tag, find_tag, culture, places, places` |
| what should I watch? Wong Kar-wai and Radiohead | `resolve_taste, resolve_taste, culture` |
| Coltrane, somewhere to drink in London | `resolve_taste, find_tag, places, places, places` |
| quiet cafe in Mumbai, I like Murakami | `resolve_taste, places` |

Three things there are worth pointing at. Asking what to watch produced no place lookups at
all, because it isn't a going-out question. The London run passed a music genre where a
cuisine was expected, got nothing back, and re-queried on its own. And a narrow cafe question
cost two calls where a night out cost five.

## What I learned about the Qloo API

Most of this cost me a wrong answer first. It's all in the code as comments, but briefly:

**Cuisine tags go in `filter.tags`, not `signal.interests.tags`.** As a signal you get a
confident-looking list of the wrong restaurants. As a filter, `urn:tag:cuisine:qloo:kashmiri`
in Delhi gives you Matamaal and Samavar, which is correct. I spent a while believing Qloo was
ignoring the tag before realising I was holding it wrong.

**Music genre tags work both ways, and the two answer different questions.** The qawwali tag
as `filter.tags` returns Nusrat Fateh Ali Khan and the Sabri Brothers, people who *are*
qawwali singers. The same tag as `signal.interests.tags` returns Junaid Jamshed and Tina Sani,
who qawwali listeners *also* listen to. Both are useful. Note this is the opposite of how
cuisine tags behave, so the rule is per tag family rather than general.

**Place queries need a category.** Without one, a query seeded on music comes back with
museums, shopping malls, and on one occasion a cake delivery website.

**Don't stack tags from different families in one filter.** Kashmiri plus restaurant together
returns junk. Kashmiri alone is fine.

**Affinity scores are not comparable between calls.** One call came back 1.0 for every result;
another spanned 0.993 to 0.995. They rank within a single response and nothing more, so the
app never shows them. Presenting them as percentages would imply a precision that isn't there.

**`/search` will happily match another continent.** A query for a Delhi cafe matched one in
Moscow, so place lookups pass a city.

`scripts/probe_qloo.py` is the script I used to work most of this out.

## Running it

```bash
pip install -r requirements.txt
cp .env.example .env        # then add your keys

python -m src.cli "I like qawwali and Kashmiri food, going out with friends in Delhi"
python -m src.cli --trace "..."          # plus every call the agent chose to make
streamlit run streamlit_app.py           # the web app
```

Without a `QLOO_API_KEY` it runs on sample data so it still does something.

### Layout

```
src/core/     the engine. Nothing in here imports streamlit.
  qloo.py       the API client, with the rules above baked in
  tools.py      those operations described so a model can call them
  loop.py       the agent loop
  llm.py        Gemini over REST
  cache.py      disk cache for both
src/cli.py    command line
streamlit_app.py   the web app, which only renders what core returns
scripts/      the probe script and the gate test
```

Responses are cached to disk. Streamlit re-runs the whole script on every click, so an
in-memory cache would be thrown away constantly, and the free Gemini tier has little room to
spare.

## Honest limitations

**Most of the testing is one person's taste.** Mine, mostly in Delhi. The venue results in
New York and London hold up, but I can't claim this generalises until more people have
pushed their own tastes through it.

**It runs on free tiers, and they are tight.** Flash-Lite gets 500 requests a day where the
full Flash models get 20, which is why the code picks Lite even though it's a little slower.
Qloo times out often enough that every call retries.

**Free-tier Gemini terms matter.** Google uses free-tier input and output to improve its
products and human reviewers may read it, so the app says so before you type anything, and
asks you not to enter anything personal.

## Licence

MIT. See [LICENSE](LICENSE).
