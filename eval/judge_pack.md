You are judging two versions of a museum-guide AI. Both got the same request from a visitor to
The Met. Judge only what is on the page; you do not need to check facts against outside sources,
but do flag anything that reads as made up, wrong, or unsupported by its citation tags.

Score each tour from 1 (poor) to 5 (excellent) on:
1. relevance: do the stops fit the request (the interests and the time given)?
2. explanation: would a curious non-expert understand what each object is and why it matters?
   Are unfamiliar names and terms explained?
3. grounding: does every fact carry a source tag ([met:…], [wikipedia:…], [data])? Any claims that
   look unsupported?
4. look_for: are the "Look for" lines concrete and useful in front of the object?
5. writing: warm, clear, and pleasant to hear read aloud; no hype words or filler.
6. completeness: does every stop have a real story (not a stub)? Is the route usable?

Then say which tour is better overall, or "tie", and whether the difference is small, clear or large.

Answer with JSON only:
{"A": {"relevance": n, "explanation": n, "grounding": n, "look_for": n, "writing": n, "completeness": n},
 "B": {...same keys...},
 "better": "A" | "B" | "tie",
 "difference": "none" | "small" | "clear" | "large",
 "reasons": "three or four sentences",
 "weakest_stops": {"A": ["stop numbers"], "B": ["stop numbers"]}}

## The visitor's request

I have an hour and love animals, especially cats and horses. Plan me a tour.

## Tour A

## Cats and Horses through the Ages
This tour explores how different cultures have honored, protected, and played with cats and horses throughout history [met:544118] [met:22757]. You will encounter bronze containers crafted for Egyptian felines, heavy steel armor designed to shield Italian warhorses, and clay companions made to join Chinese riders in the afterlife [met:544118] [met:22757] [met:42189]. From mischievous household pranks to busy Parisian horse markets, these works capture the many ways we share our lives with animals [met:435852] [met:435702].
### 1. Cat Statuette intended to contain a mummified cat — Gallery 134
*Egyptian, 332–30 BCE* · about 3 min in

This hollow bronze statuette of a cat once served as a sacred container for a mummified feline [met:544118][wikipedia:Cats in ancient Egypt]. Ancient Egyptian craftsmen cast this animal figure from leaded bronze during the Ptolemaic Period, between 332 and 30 BCE [met:544118]. The Ptolemaic Period was an era when a Greek dynasty founded by one of Alexander the Great's generals ruled Egypt [wikipedia:Ptolemaic Kingdom]. To gain acceptance from native Egyptians, these foreign rulers took the local title of pharaoh [wikipedia:Ptolemaic Kingdom]. During this time, Egyptians associated domestic cats with Bastet, a goddess of fertility, justice, and protection who was represented with feline features [wikipedia:Cats in ancient Egypt]. This association made animal mummification extremely popular across the region [wikipedia:Cats in ancient Egypt]. Visiting pilgrims would buy animal mummies or hollow statuettes to offer to the deities at temple sites [wikipedia:Cats in ancient Egypt]. They presented these objects as votive offerings, often during large festivals and religious pilgrimages [wikipedia:Cats in ancient Egypt]. Temples are believed to have systematically bred cats to be mummified and placed inside these bronze containers [wikipedia:Cats in ancient Egypt]. Protecting felines was so important that killing a cat was considered a serious crime, and an outraged crowd once even lynched a Roman for doing so [wikipedia:Cats in ancient Egypt]. This statuette remains an exceptional example of how artistic skill and daily spiritual devotion came together to honor a beloved animal [met:544118][wikipedia:Cats in ancient Egypt].

Look for: the metal tangs at the base, which were used to mount the statuette [met:544118]

### 2. Horse Armor Probably Made for Count  Antonio IV Collalto (1548–1620) — Gallery 371
*Italian, probably Brescia, ca. 1580–90 and later* · about 15 min in

This complete suit of steel plates is body armor for a horse, designed to protect a mount during battle or a parade [met:22757][wikipedia:Barding]. It was crafted from steel, leather, copper alloy, and textile in Italy, probably in Brescia, around 1580 to 1590 [met:22757]. The entire defensive ensemble is very heavy, weighing over ninety-three pounds including the saddle [met:22757]. Historically, body armor for war horses is called barding [wikipedia:Barding]. Barding originally developed because as knights became better protected, their horses became vulnerable targets for archers and infantrymen [wikipedia:Barding]. However, full sets of steel barding were highly expensive, and only the richest knights could afford them [wikipedia:Barding]. They served as elite status symbols, transforming a warhorse into a moving sculpture to show off a ruler's power [wikipedia:Barding]. This particular set was probably made for Count Antonio IV Collalto, who belonged to the House of Collalto [met:22757][wikipedia:Collalto family]. The House of Collalto is an old, distinguished noble house of Lombard origin, named after their seat in Italy, where their first documents date back to the tenth century [wikipedia:Collalto family]. While some historical horse armor was made of hardened leather, which is especially rare today, surviving period examples of any horse armor are very rare [wikipedia:Barding]. This set demonstrates how the wealthiest knights used expensive armor to protect their mounts and display their power [wikipedia:Barding].

Look for: the steel plates and the saddle, which together weigh over ninety-three pounds [met:22757]

### 3. 唐  三彩陶馬|Horse — Gallery 207
*China, late 7th–first half of the 8th century* · about 30 min in

This clay sculpture of a horse was created to accompany a wealthy Chinese person into the afterlife, serving as a ride in a personalized paradise [met:42189] [wikipedia:Tang dynasty tomb figures]. The earthenware figure was crafted in China between the late seventh and first half of the eighth century during the Tang dynasty, an imperial dynasty that ruled from 618 to 907 [met:42189] [wikipedia:Tang dynasty]. It features a three-color decoration called sancai, a low-temperature glazing technique that uses metal oxides of copper and iron to produce flowing shades of green, amber-brown, and creamy off-white [met:42189] [wikipedia:Sancai]. In Tang society, horses were highly prized by people of high rank for travel, hunting, and military campaigns [wikipedia:Tang dynasty tomb figures]. For a grand burial, the elite commissioned these pottery figures, known as mingqi, to be paraded in the funeral procession and then placed in the tomb chambers [wikipedia:Tang dynasty tomb figures]. Only the upper classes were permitted to use sancai-glazed figures, which were made in multiple molded sections and assembled with great realism [wikipedia:Sancai] [wikipedia:Tang dynasty tomb figures]. This horse reflects the height of Tang ceramic mastery, a peak of production that ended abruptly in 755 with a highly disruptive rebellion that devastated the region's elite and the kilns that supplied them [wikipedia:Sancai] [wikipedia:Tang dynasty tomb figures].

Look for: the three-color glaze and pigment on this earthenware horse [met:42189]

### 4. Two Children Teasing a Cat — Gallery 637
*Annibale Carracci, 1587–88* · about 42 min in

This painting captures a suspenseful, mischievous moment just before a prank goes wrong [wikipedia:Two Children Teasing a Cat]. It shows a boy and a girl playfully provoking a cat with a crayfish [met:435852], trying to insert its claw into the ear of the wary animal [wikipedia:Two Children Teasing a Cat]. The Italian artist Annibale Carracci painted this oil on canvas around 1587 to 1588 [met:435852], [wikipedia:Two Children Teasing a Cat]. During this period, Carracci is known to have stayed in Venice, where he was influenced by Venetian artists and their glimmering colors [wikipedia:Annibale Carracci], [wikipedia:Two Children Teasing a Cat]. He painted this work in his youth, when he focused on genre painting, which depicts aspects of everyday life by portraying ordinary people engaged in common activities [wikipedia:Genre painting], [wikipedia:Two Children Teasing a Cat]. The composition was inspired by a drawing by the artist Sofonisba Anguissola [wikipedia:Two Children Teasing a Cat]. However, while other artists showed the painful consequences after a bite, Carracci froze the action just before the reaction occurs, leaving the viewer in suspense [wikipedia:Two Children Teasing a Cat]. The scene likely carried a mild moral warning, following the example of Flemish paintings that cautioned viewers to think of the consequences of reckless actions [wikipedia:Two Children Teasing a Cat]. The composition became very popular, inspiring several other artists to create works based on this scene [wikipedia:Two Children Teasing a Cat].

Look for: the boy and girl playfully provoking the cat, and the crayfish they are using to tease it [met:435852]

### 5. The Silver Tureen — Gallery 629
*Jean Siméon Chardin, ca. 1728–30* · about 50 min in

This painting depicts a still life scene where a cat eyes a silver serving dish, fruit, and hunted game [met:435887]. The French artist Jean Siméon Chardin created this oil painting on canvas around 1728 to 1730 [met:435887]. It is a still life, which is a type of artwork that depicts mostly inanimate, commonplace objects like food, plants, and dead animals [wikipedia:Still life]. Chardin was an eighteenth-century Parisian painter who became known for his realistic depictions of everyday domestic life and household objects [wikipedia:Jean Siméon Chardin]. During his era, still life paintings were considered minor works of art by the royal academy, which favored historical and religious subjects instead [wikipedia:Jean Siméon Chardin] [wikipedia:Still life]. However, Chardin's paintings were highly sought after by buyers and even the French king [wikipedia:Jean Siméon Chardin] [wikipedia:Still life]. He worked very slowly and painted only a few pictures each year, focusing on balanced compositions and the soft diffusion of light [wikipedia:Jean Siméon Chardin]. This work is unusual because it includes a live, alert cat amidst the silent, motionless objects [met:435887] [wikipedia:Still life]. Chardin carefully contrasts the textures of the metallic tureen, the soft fur of a rabbit, the feathers of game birds, and the apples [met:435887] [wikipedia:Jean Siméon Chardin].

Look for: the cat eyeing the scene, the silver tureen, the rabbit, the birds, and the apples [met:435887]

### 6. The Horse Fair — Gallery 812
*Rosa Bonheur, 1852–55* · about 62 min in

This enormous painting brings to life the busy atmosphere of a nineteenth-century Paris horse market [met:435702, wikipedia:The Horse Fair]. It was painted in oil on canvas by the French artist Rosa Bonheur between 1852 and 1855 [met:435702]. Bonheur worked as an animalier, a French term for an artist who specializes in realistic animal subjects [wikipedia:Rosa Bonheur]. To paint these powerful Percherons, a French breed of heavy draft horses, she visited the market on the Boulevard de l'Hôpital twice a week for a year and a half [wikipedia:The Horse Fair]. Because women faced harassment in these rough environments, she obtained official police permission to dress in men's trousers and painters' smocks so she could sketch without drawing attention to herself [wikipedia:The Horse Fair]. She broke from traditional styles by painting the horses' eyes exactly as they appeared in life, rather than giving them human-like expressions to create artificial emotion [wikipedia:The Horse Fair]. Some scholars even believe she included herself in the crowd as a self-portrait [wikipedia:The Horse Fair]. Her devotion to realism made this monumental canvas widely praised, leading to a meeting with Queen Victoria and establishing her as a highly recognized artist of her century [wikipedia:The Horse Fair, wikipedia:Rosa Bonheur].

Look for: the massive scale of the canvas showing men and horses in Paris [met:435702]

## Extras, if you have time

### 7. Three Jockeys — Gallery 817
*Edgar Degas, ca. 1900* · about 70 min in

This drawing captures a fleeting, active moment on the racetrack, showing three jockeys on their horses [met:436164], [wikipedia:Before the Race]. It is a pastel drawing on tracing paper, mounted on board, made around 1900 by the French artist Edgar Degas [met:436164]. Degas was a founder of Impressionism, a nineteenth-century French art movement, and was a skilled draftsman known for depicting movement in modern life [wikipedia:Edgar Degas]. While he is highly associated with ballet dancers, Degas also loved horse racing, which became a popular pastime in France during his lifetime [wikipedia:Before the Race], [wikipedia:Edgar Degas]. He visited breeding farms in Normandy and filled his notebooks with drawings to know horses in anatomical detail [wikipedia:Before the Race]. For this work, he used pastels, which are dry drawing materials, and tracing paper, which is a translucent paper designed to let light pass through so an artist can easily copy or trace drawings [met:436164], [wikipedia:Edgar Degas], [wikipedia:Tracing paper]. This piece is special because it showcases Degas's skill in rendering motion [wikipedia:Edgar Degas]. By utilizing pastels, he made the scene look highly spontaneous, successfully capturing the energy of a passing moment [wikipedia:Before the Race], [wikipedia:Edgar Degas].

Look for: the three men riding horses, and the texture of the pastel on the tracing paper, which is mounted on a board [met:436164]

### 8. 唐 彩繪泥塑騎馬仕女俑|Horse and female rider — Gallery 207
*China, 7th century* · about 82 min in

This clay sculpture depicts a horse and its female rider, showing a scene of courtly life from early China [met:42124]. Created in China during the seventh century, the figure is made of unfired clay painted with pigment [met:42124]. It belongs to a class of grave goods known as mingqi, which were clay or pottery figures placed inside Chinese tombs [met:42124][wikipedia:Tang dynasty tomb figures]. During the Tang dynasty, a period from 618 to 907 that is regarded as a high point of Chinese civilization, people believed that these figures would become available to serve the deceased in the afterlife [met:42124][wikipedia:Tang dynasty tomb figures][wikipedia:Tang dynasty]. To recreate a comfortable paradise for the spirit of the deceased, families filled tombs with figures of servants, musicians, and animals, with horses being the most common choice [wikipedia:Tang dynasty tomb figures]. These figures were paraded on carts during the funeral procession, and then arranged along the sloping access way to the underground burial chamber [wikipedia:Tang dynasty tomb figures]. There, the saddled horses stood waiting to carry the deceased on excursions or hunts [wikipedia:Tang dynasty tomb figures]. This sculpture is unusual because it is made of delicate, unfired clay rather than fired earthenware [met:42124][wikipedia:Tang dynasty tomb figures]. While many other tomb figures were coated in durable ceramic glazes, the painted pigment on this unfired clay is much more fragile and rarely survived [met:42124][wikipedia:Tang dynasty tomb figures].

Look for: the remains of painted pigment on the unfired clay surfaces of the horse and its female rider [met:42124]

### 9. 明  玉雕馬上封侯|Horse and monkey — Gallery 222
*China, 17th century* · about 90 min in

This sculpture depicts a horse and a monkey resting together, presenting a traditional Chinese visual pun for wishing someone a rapid career promotion [met:43251, wikipedia:Simians in Chinese culture]. It is a small figure carved from nephrite jade in China during the seventeenth century, during the Ming dynasty [met:43251]. The Ming dynasty, which ruled China from 1368 to 1644, was a period when arts like jade carving flourished [met:43251]. Nephrite is the primary hardstone of Chinese sculpture, deeply prized for its durability, beauty, and symbolic connection to the human soul [wikipedia:Chinese jade]. This sculpture plays on a linguistic pun called a rebus, which is a visual representation of a spoken phrase using images [wikipedia:Wufu]. In Chinese, the words for on horseback sound exactly like immediately, while the word for monkey sounds identical to marquis, a high noble rank [wikipedia:Simians in Chinese culture]. Therefore, showing a monkey riding a horse creates the popular auspicious phrase mashang fenghou, which translates to a wish that the recipient is immediately promoted to a high office [wikipedia:Simians in Chinese culture]. This carving is significant because it transforms a hard, precious stone into a warm, playful scene of animal companionship that carried a highly desirable social message for the ruling elite [wikipedia:Chinese jade, wikipedia:Simians in Chinese culture].

Look for: the small monkey clinging to the back of the resting horse, carved from a single block of pale nephrite jade [met:43251]
### Before you go
- Walking times are estimates from a simple model of the building (galleries grouped into wings and floors), not a real floor plan.
- The main route takes about 68 min, a little over the 60 min you have.
- Also on theme, but left out to avoid doubling back: Figure of a Seated Cat (gallery 130); Parade Saddle (gallery 373)
- The Met's live API did not answer for some stops; their galleries come from the snapshot.
- We do not know for certain if the artist Rosa Bonheur painted herself in the crowd of her scene depicting the Paris horse market [met:435702].
- The records cannot confirm with absolute certainty whether the steel horse armor was made for Count Antonio IV Collalto [met:22757].
- The collection data does not explain why Edgar Degas chose to use tracing paper for his racetrack drawing [met:436164].

## Tour B

## Horses and Cats of the Met
This tour explores how humans have worked with, honored, and lived alongside horses and cats across the centuries [met:22757, met:544118]. You will see horses outfitted in heavy steel armor and intricately carved bone to display their owners' elite power and status [met:22757, wikipedia:Barding, met:21991, wikipedia:Saddle]. You will also meet cats captured in moments of quiet suspense or revered as sacred, protective companions [met:435852, met:435887, wikipedia:Cats in ancient Egypt].

### 1. Horse Armor Probably Made for Count  Antonio IV Collalto (1548–1620) — Gallery 371
*Italian, probably Brescia, ca. 1580–90 and later* · about 3 min in

This complete set of armor, known as a bard, was designed to protect a warhorse in battle, transforming the animal into an armored, moving sculpture [met:22757, wikipedia:Barding]. Probably crafted in Brescia, Italy, around 1580 to 1590, this set is made of steel, leather, copper alloy, and textiles, and it weighs over ninety-three pounds including the saddle [met:22757]. During the late Middle Ages, as armor protection for knights became more effective, enemies targeted horses to disable and dismount their riders, which led to the development of barding, or horse armor [wikipedia:Barding]. This defense system was likely made for Count Antonio IV Collalto, an Italian nobleman who lived from 1548 to 1620 [met:22757]. Only the wealthiest figures could afford a full set of barding [wikipedia:Barding]. Beyond protecting an expensive and highly trained animal in combat, such extensive armor transformed the horse into a grand display of its owner's power and elite status [wikipedia:Barding]. Surviving complete historical sets are extremely rare today, making this massive, beautifully coordinated assembly an exceptional look at historic horse armor [met:22757, wikipedia:Barding].

Look for: the steel plates of the horse armor, the saddle, and the leather straps and copper alloy fittings that hold them together [met:22757]

### 2. Parade Saddle — Gallery 373
*German or Tyrolean, ca. 1450* · about 10 min in

This object is a parade saddle used to equip horses for ceremonial display [met:21991]. Created around 1450, this saddle is constructed from bone, wood, and leather [met:21991]. It is attributed to German or Tyrolean craftspeople [met:21991]. Tyrol was an estate of the Holy Roman Empire that was ruled by the House of Habsburg starting in 1363 [wikipedia:County of Tyrol]. Since ancient times, saddles functioned as status symbols, and owners added elaborate decorations to show off their wealth and high rank [wikipedia:Saddle]. To build a saddle, a maker started with a supportive wooden base called a tree and covered it with other materials like leather and decorative parts [wikipedia:Saddle]. What makes this parade saddle unusual is the extensive bone carving that covers its exterior [met:21991]. These intricate bone carvings depict figures of men, women, horses, and mythical unicorns [met:21991].

Look for: the intricate carvings depicting men, women, horses, and mythical unicorns on the bone exterior [met:21991]

### 3. The Horse Fair — Gallery 812
*Rosa Bonheur, 1852–55* · about 25 min in

This monumental painting places you right in the middle of a bustling market in Paris, capturing the raw power and motion of horses [met:435702, wikipedia:The Horse Fair]. It is an oil-on-canvas work created between 1852 and 1855 by Rosa Bonheur, the most famous female painter of the nineteenth century [met:435702, wikipedia:Rosa Bonheur]. Bonheur worked as an animalier, a French term for an artist who specializes in depicting animals [wikipedia:Rosa Bonheur]. To paint these heavy Percheron draft horses realistically, she sketched twice a week for a year and a half at the market [wikipedia:The Horse Fair]. To avoid drawing attention to herself in this male-dominated crowd, she even obtained permission from the Paris police to dress in men's trousers and coats [wikipedia:The Horse Fair]. She broke with the artistic traditions of her time by refusing to give the animals humanlike expressions [wikipedia:The Horse Fair]. Instead, she relied on her rigorous studies of veterinary anatomy to paint their eyes and muscles exactly as they were in life [wikipedia:Rosa Bonheur, wikipedia:The Horse Fair]. Her dynamic style was inspired by ancient Greek sculptures like the Parthenon Frieze, a famous band of relief sculptures showing a procession [wikipedia:The Horse Fair]. The painting's colossal scale and energy made it a sensation at the 1853 Paris Salon art exhibition, launching her to international stardom [wikipedia:The Horse Fair, wikipedia:Rosa Bonheur].

Look for: the dome of the Salpêtrière hospital in the left background, the powerful draft horses rearing and turning, and the rider in the center who may be a self-portrait of the artist [wikipedia:The Horse Fair] [met:435702]

### 4. Two Children Teasing a Cat — Gallery 637
*Annibale Carracci, 1587–88* · about 37 min in

This painting captures a tense, mischievous moment just before a prank goes wrong [wikipedia:Two Children Teasing a Cat]. Painted with oil on canvas, it was created around 1587 to 1588 by the Italian artist Annibale Carracci [met:435852]. During his youth in Bologna, Carracci painted several genre works, which are scenes of everyday life rather than grand historical subjects [wikipedia:Two Children Teasing a Cat, wikipedia:Annibale Carracci]. The informal, lively style of this piece reflects the influence of Venetian artists whom Carracci studied during his travels in northern Italy [wikipedia:Two Children Teasing a Cat, wikipedia:Annibale Carracci]. Here, a boy and a girl try to prank their pet [met:435852, wikipedia:Two Children Teasing a Cat]. The boy holds a shrimp, or small shellfish, and tries to stick its sharp claw into the ear of a wary cat [wikipedia:Two Children Teasing a Cat]. Other artists of the era painted the painful aftermath of playing with animals, such as children crying after being bitten [wikipedia:Two Children Teasing a Cat]. In contrast, Carracci focuses entirely on the suspense, freezing the action at the very second before the cat reacts [wikipedia:Two Children Teasing a Cat]. This humorous painting may have also served as a mild moral warning to viewers, reminding them to think about the painful consequences of reckless actions [wikipedia:Two Children Teasing a Cat].

Look for: the wary, tense posture of the cat and the boy's fingers gently holding the small shrimp claw right beside its ear [wikipedia:Two Children Teasing a Cat] [met:435852]

### 5. The Silver Tureen — Gallery 629
*Jean Siméon Chardin, ca. 1728–30* · about 45 min in

This painting captures a moment of playful tension, showing an inquisitive cat eyeing a kitchen table piled with food [met:435887]. It is an oil on canvas painted around 1728 to 1730 by Jean Siméon Chardin, a French artist who lived and worked in Paris and became a master of still life [met:435887, wikipedia:Jean Siméon Chardin]. Chardin's early popularity was built on detailed paintings of animals and fruit [wikipedia:Jean Siméon Chardin]. Unlike the elaborate and decorative Rococo style that dominated French art in the eighteenth century, Chardin chose to focus on quiet, beautifully textured household scenes [wikipedia:Jean Siméon Chardin]. He worked very slowly, creating only about four paintings a year over his career [wikipedia:Jean Siméon Chardin]. This scene displays a bountiful arrangement of game birds, apples, a rabbit, and a silver tureen, which is a deep, covered vessel used for serving soup [met:435887, wikipedia:Tureen]. By adding a live, stalking cat to the traditional still life, Chardin brings a sense of life, movement, and lighthearted suspense to what would otherwise be a silent, static display of kitchen ingredients [met:435887, wikipedia:Jean Siméon Chardin].

Look for: the inquisitive cat crouching on the left side of the table, eyeing the display of game birds, fruit, and the polished silver tureen [met:435887]

### 6. Cat Statuette intended to contain a mummified cat — Gallery 134
*Egyptian, 332–30 BCE* · about 60 min in

This sleek sculpture of a seated cat was created in ancient Egypt to serve as a sacred coffin for a mummified cat [met:544118]. Craftspeople cast this hollow container from leaded bronze between 332 and 30 BCE [met:544118]. This was during the Ptolemaic Period, an era when a dynasty of Greek kings ruled Egypt following the conquests of Alexander the Great [wikipedia:Ptolemaic Kingdom]. In ancient Egypt, domestic cats were highly revered and closely associated with Bastet, the goddess of fertility and protection [wikipedia:Cats in ancient Egypt]. During this time, pilgrims frequently bought mummified animals and placed them inside specialized containers as votive offerings, which were holy gifts presented to the gods to carry a person's prayers directly to the deity [wikipedia:Cats in ancient Egypt]. This practice became so popular that temples bred and mummified cats on a massive scale, which supported an entire economy of breeders, embalmers, and artists [wikipedia:Cats in ancient Egypt]. Craftspeople made these statues in various sizes and materials, ranging from cheap clay to expensive hollow bronze, depending on what the buyer could afford [wikipedia:Cats in ancient Egypt]. This statuette is remarkable for its lifelike poise, which shows the great skill of the ancient metalworkers [met:544118].

Look for: the metal mounting pins, known as tangs, extending from the bottom of the paws [met:544118]

## Extras, if you have time

### 7. Figure of a Seated Cat — Gallery 130
*Egyptian, 664–30 BCE* · about 68 min in

This statuette depicts a seated cat, representing the animal that ancient Egyptians associated with their protective goddess Bastet [met:329961, wikipedia:Cats in ancient Egypt]. It is made of cupreous alloy, a copper-based metal, and dates to between 664 and 30 BCE [met:329961]. This span of centuries covers Egypt's Late Period, which was the final era of native Egyptian pharaohs, as well as the subsequent Ptolemaic Period, when a Greek dynasty founded by a general of Alexander the Great ruled the region [met:329961, wikipedia:Late Period of Egypt, wikipedia:Ptolemaic Kingdom]. During these centuries, animal cults flourished across Egypt, and cats were deeply revered as vital household protectors that kept pests and venomous snakes away [wikipedia:Late Period of Egypt, wikipedia:Cats in ancient Egypt]. Devotees frequently dedicated small metal statues like this one to Bastet at her temples, hoping to earn her blessings of fertility and safety [wikipedia:Cats in ancient Egypt]. This figure shows how cats transitioned from helpful working animals to sacred companions, reflecting a religious devotion so intense that harming a cat, even by accident, was considered a major crime that could result in execution by an angry public [wikipedia:Cats in ancient Egypt].

Look for: the classic, upright seated posture of the metal feline [met:329961]

### 8. Lion Cub — Gallery 101
*Egyptian, ca. 3100–2900 BCE* · about 78 min in

This statuette depicts a young lion cub from the very beginning of ancient Egyptian history [met:544077]. It was carved from quartzite, an extremely hard and durable metamorphic rock, during Dynasty 1 of the Early Dynastic Period, around 3100 to 2900 BCE [met:544077, wikipedia:Quartzite]. This era represents the first series of Egyptian kings to rule over a unified Upper and Lower Egypt, a time when written hieroglyphs were still in their earliest stages [wikipedia:First Dynasty of Egypt]. While early monumental structures of this dynasty were built largely of wood and mud bricks, stone was selectively used for ornaments, vessels, and occasionally, statues [wikipedia:First Dynasty of Egypt]. Because quartzite is incredibly hard and fractures directly across its individual quartz grains rather than around them, carving it required immense patience and skill [wikipedia:Quartzite]. The sculptor successfully overcame the physical resistance of this durable stone to capture the compact form of a lion cub [met:544077, wikipedia:Quartzite].

Look for: the compact, rounded shape of the lion cub carved from hard quartzite [met:544077]

### Before you go
- Walking times are estimates from a simple model of the building (galleries grouped into wings and floors), not a real floor plan.
- The main route takes about 66 min, a little over the 60 min you have.
- Also on theme, but left out to avoid doubling back: Relief (gallery 235); The Return to Court of the Four Graybeards of Mount Shang (right); Su Shi’s Visit to the Wind and Water Cave (left) (gallery 226)
* The data cannot show you how the gallery lighting catches the details of the carved bone on the parade saddle [met:21991].
* The data cannot convey the true scale and physical presence of the colossal horse painting [met:435702].
* The files do not describe how the painted cats compare to the real-life pets you know [met:435852, met:435887].
