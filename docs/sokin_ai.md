
---

## 📌 Poslovni model i tržišni kontekst (B2B i globalna plaćanja)

* **Klijenti i potrebe:** B2B klijenti posluju na globalnom tržištu i žele opciju plaćanja u stranim valutama, a ne samo u lokalnim.
* **Percepcija javnosti:** Kao obični potrošači nismo svesni kompleksnosti globalnih plaćanja. Milioni cirkulišu sistemom, a za male iznose često nema transakcionih naknada.
* **Problem likvidnosti:** Na nekim tržištima ne postoje veliki fondovi likvidnosti (liquidity pools), pa je potrebno balansirati transakcije iz valute u valutu, ili čak zlato-valuta. Novac je uvek potreban lokalno.
* **Investicije:** Sredstva iz *funding round*-a (runde finansiranja) koriste se isključivo za rast i razvoj biznisa.

---

## 🛡️ AML, KYB i usklađenost sa regulativama (Compliance)

### 👥 Profili rizika i provere (Counterparties)

* **Regionalni rizik:** Faktori na koje se obraća pažnja zavise od regiona. Prate se liste sankcija i politički izložene osobe (PEP – političari, direktori itd.).
* **Evropska unija (EU):** Fokus je na sprečavanju finansiranja terorizma i proceni nivoa rizika za odlazne transakcije.
* **Razlika u kompleksnosti:** Provera fizičkih lica (građana) je jednostavna. Kod kompanija (**KYB**) proces je komplikovan: *Ko zapravo stoji iza firme? Koje sve kompanije stoje iza kompanije koja vrši transakciju?*
* **Verifikacija primaoca:** Uvode se napredne usluge provere primaoca plaćanja (*Verification of the Payee*).

### 🔍 AML sistem i procesi rada

* **Odlazni novac (Money Out):** Rade se inicijalne provere pre izvršenja. Da li možemo da realizujemo plaćanje? Da li se podaci o primaocu poklapaju? Da li su podaci tačni i da li imamo pokriće u sredstvima? Ako nešto sumnjivo postoji, šalje se timu za usklađenost (*Compliance team*) na odobrenje.
* **Trenutno stanje:** "Stop and wait" model koji pokreće AML engine. Primenjuje se pristup zasnovan na riziku (*Risk-based approach*) sa obaveznom ljudskom kontrolom (*Human in the loop*).
* **Manuelni rad:** Dobar procenat transakcija je automatizovan, ali je manuelni rad i dalje prisutan kroz tzv. **4i ili 6i provere** (princip četiri ili šest očiju – više osoba mora da potpiše/odobri transakciju).
* **Etičke restrikcije:** Određeni partneri odbijaju saradnju sa biznisima koji su povezani sa kriptovalutama ili kockanjem iz etičkih razloga.

### 🚩 Indikatori rizika (Red Flags)

* **Sumnjive promene lokacije:** Ako je kompanija registrovana u SAD, a nalog za plaćanje stigne iz Kine ili Rusije, automatski se podiže nivo rizika i radi se manuelna provera odbora i vlasnika.
* **Analiza trendova:** AML sistem prati trend plaćanja kroz vreme, količinu transakcija i vremensku razliku između priliva i odliva novca.
* **Anomalije u iznosima:** Prate se interni i eksterni tokovi. Na primer, ako kompanija zarađuje 10 miliona godišnje, a iznenada joj stigne uplata od 20 miliona, to pali alarm.
* **Regulativa porekla:** Zbog striktnih regulativa, mora se tačno znati od koga novac dolazi (da li je neko treće lice izvršilo uplatu u tvoje ime).

---

## ⚙️ Tehnička arhitektura i infrastruktura

```
[Klijent / App] ──> [Push Notifikacije]
                         │
                         ▼
        [Sistem za obradu transakcija]
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
[Regija: UAE]                    [Ostale regije]
(Lokalni podaci)                  (Cloud Shards)
        │                                 │
        └───────────────┬─────────────────┘
                        ▼
            [Multi-shard Relational DB]

```

* **Migracija i skaliranje:** Prelazak sa AWS-a na Azure. Koristi se *sharding* arhitektura za pozadinske procese (background processes). Baza je *Multi-shard* relacionog tipa (Relational DB).
* **Lokalizacija podataka (UAE):** Propisi u UAE zahtevaju da se obrada podataka vrši lokalno. Kreiranje dva odvojena sistema za UAE se pokazalo kao loše rešenje.
* **Skaliranje:** Pokušaj horizontalnog skaliranja sistema doneo je **0% ubrzanja** (usko grlo je ostalo na drugom mestu).

---

## 🌍 Problemi na tržištu u razvoju i inovacije (Afrika & Kripto)

* **Problem u Africi (Treći svet):** Transakcije traju i do 3 dana. Cilj je ukloniti trenje (*friction*) iz globalnih plaćanja na ovom kontinentu.
* **Rešenje – Stablecoin:** Kripto i *stablecoins* se vide kao rešenje za Afriku, jer postoji veliki interes da se novac čuva u stabilnim valutama.
* **Tradicionalne banke:** Trenutno nijedna banka ne koristi kriptovalute, a FX (devizni) kursevi su izuzetno visoki.
* **Instant FX:** Kada se radi devizna trgovina (FX trade), ukoliko klijent ima dovoljno novca na računu, transakcija se izvršava u realnom vremenu (*real-time*).
* **Regulative:** Dugoročni cilj je dobijanje bankarskih licenci u svakom od regiona radi potpune regulisane kontrole.

---

## 🚀 Strategija razvoja proizvoda (Product Strategy)

* **Trenutni problemi:** Potrebno je olakšati nadogradnju same platforme (*easier to build on top of the platform*).
* **Lean pristup:** **"DO LESS"** – isporučiti manje poliranu funkcionalnost korisniku, brzo prikupiti podatke iz realnog korišćenja, pa na osnovu toga kreirati novu, bolju verziju (**kratak feedback loop**).
* **Push notifikacije:** Odlična stvar zbog mobilne aplikacije. Omogućavaju bolji kontakt sa korisnicima i lakše nuđenje dodatnih usluga (*side services*).
* **Novi partneri:** Pronalaženje drugih vendora koji imaju velike bilanse stanja (*balance sheet*) svojih kupaca.