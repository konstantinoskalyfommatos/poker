# Sample hand histories from other sites

Real samples collected to design site parsers on top of `ParentHandParser`.
One representative cash No Limit Hold'em hand per site.

| File | Site | Source |
| --- | --- | --- |
| `partypoker.txt` | PartyPoker | https://raw.githubusercontent.com/thlorenz/hhp/master/test/partypoker/cash.hhsmithy.usd.NLHE.9max/hands.txt |
| `888poker.txt` | 888poker (Pacific) | https://raw.githubusercontent.com/thlorenz/hhp/master/test/pacific/cash.hhsmithy.usd.nlh.6max/hands.txt |
| `fulltilt.txt` | Full Tilt | https://raw.githubusercontent.com/alexmarie/pokerbots/master/fullTiltExample.txt |
| `ggpoker.txt` | GGPoker (Rush & Cash) | https://raw.githubusercontent.com/LayorX/GGPoker-Hand-Analyzer/main/demo_data/10000_data/GG20250808-1932%20-%20RushAndCash10539634%20-%200.02%20-%200.05%20-%206max.txt |
| `ignition.txt` | Ignition/Bodog (Zone) | https://raw.githubusercontent.com/thlorenz/hhp/master/test/fixtures/holdem/ignition/cash.zone.txt |
| `ipoker.xml` | iPoker (Playtech: bet365, William Hill) | https://raw.githubusercontent.com/jeurju/fpdb-3/master/regression-test-files/cash/iPoker/Flop/NLHE-USD-0.05-0.10-201312.player.antes.then.sits.out.txt |

Notes:

- iPoker no longer exports text; the client writes XML (one `<game>` per hand
  inside a `<session>`), so it will need a different loader than the text
  parsers.
- Full sources for PartyPoker/888/GGPoker hold multi-hand files; the saved
  excerpt is the first hand of each.
- Useful extra sample sets: GGPoker tourney hands in
  https://github.com/matthiola0/poker-hand-review (`tests/test_hand_parser.py`),
  more hhp fixtures at https://github.com/thlorenz/hhp.
