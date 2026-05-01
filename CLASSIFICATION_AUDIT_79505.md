# Audit of 79,505 Classified Articles

Generated from `docs/explorer_data.json`.

## Totals

- Audited articles: `79,505`
- `official=True`: `18,513` (`23.29%`)
- `parket=True`: `4,167` (`5.24%`)
- `balance=True`: `4,867` (`6.12%`)

## Internal Consistency

- `pk_without_of`: `0`
- `br_without_of`: `0`
- `pk_with_noc_gt_0`: `0`
- `pk_with_sc_gt_1`: `0`
- `br_with_noc_gt_0`: `0`

## Period Summary

| Period | N | Official | Parket | Balance |
| --- | ---: | ---: | ---: | ---: |
| `p0` | `27,916` | `6,832` | `1,640` | `1,877` |
| `p1` | `26,342` | `6,120` | `1,349` | `1,584` |
| `p2` | `25,247` | `5,561` | `1,178` | `1,406` |

## Main Risk Buckets

- `parket` with `source_count=0`: `2,625` (`62.99%` of all `parket`)
- `parket` with `source_count=1`: `1,542` (`37.01%` of all `parket`)
- `parket` inside `ATO`: `1,325`
- `parket` in `regions` with `source_count=0`: `403`
- `parket` in foreign-context titles/URLs: `1,200`
- `parket` in foreign-context titles/URLs with `source_count=0`: `758`
- `parket` in foreign-context minister titles/URLs: `18`
- `official=False` but `official_source_count>0`: `17,816`
- `official=True` but `official_source_count=0`: `9,427`
- `official=True` and `source_count=0`: `2,625`

## `parket` by Rubric

| Rubric | Parket | Total | Parket % |
| --- | ---: | ---: | ---: |
| `ato` | `1,325` | `21,906` | `6.05%` |
| `economy` | `734` | `11,905` | `6.17%` |
| `society` | `719` | `10,619` | `6.77%` |
| `polytics` | `716` | `11,491` | `6.23%` |
| `regions` | `612` | `20,899` | `2.93%` |
| `vidbudova` | `52` | `2,304` | `2.26%` |
| `tymchasovo-okupovani` | `9` | `381` | `2.36%` |

## Derived Official Categories from URL Slugs

| Category | Official | Parket | Balance |
| --- | ---: | ---: | ---: |
| Президент / ОП | `6,140` | `803` | `931` |
| Силовий блок | `4,774` | `1,472` | `1,691` |
| Міністерства | `3,656` | `649` | `801` |
| Держструктури / держкомпанії | `1,409` | `512` | `646` |
| Уряд / Кабмін | `1,257` | `329` | `365` |
| Парламент | `1,235` | `267` | `287` |
| Регіональна влада | `948` | `315` | `369` |

## `parket` with `source_count=0`: simple title heuristics

- `zvedennya`: `200`
- `za_dobu`: `325`
- `ova_or_kmva`: `424`
- `zsu_or_genshtab_or_sbu`: `753`
- `president_or_rada`: `641`

## Sample: pk_sc0_foreignish

| Date | Period | Rubric | sc | oc | noc | Title |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `2023-05-01` | `p0` | `ato` | `0` | `0` | `0` | [ЗСУ знищили вже 190 960 російських загарбників](https://www.ukrinform.ua/rubric-ato/3702941-zsu-znisili-vze-190-960-rosijskih-zagarbnikiv.html) |
| `2023-05-01` | `p0` | `regions` | `0` | `0` | `0` | [росіяни за добу атакували 11 областей України - зведення ОВА](https://www.ukrinform.ua/rubric-regions/3703012-rosiani-za-dobu-atakuvali-11-oblastej-ukraini-zvedenna-ova.html) |
| `2023-05-02` | `p0` | `economy` | `0` | `0` | `0` | [Заборона на рибу і деревину з росії: Рада закликає світ розширити санкції](https://www.ukrinform.ua/rubric-economy/3703814-zaborona-na-ribu-i-derevinu-z-rosii-rada-zaklikae-svit-rozsiriti-sankcii.html) |
| `2023-05-02` | `p0` | `regions` | `0` | `0` | `0` | [росіяни за добу обстріляли дев'ять областей України - зведення ОВА](https://www.ukrinform.ua/rubric-regions/3703575-rosiani-za-dobu-obstrilali-devat-oblastej-ukraini-zvedenna-ova.html) |
| `2023-05-02` | `p0` | `society` | `0` | `0` | `0` | [СБУ викрила ділків, які профінансували бойовиків «днр» більш як на ₴50 мільйонів](https://www.ukrinform.ua/rubric-society/3703640-sbu-vikrila-dilkiv-aki-profinansuvali-bojovikiv-dnr-bils-ak-na-50-miljoniv.html) |
| `2023-05-03` | `p0` | `ato` | `0` | `0` | `0` | [ЗСУ ліквідували вже 191 940 російських загарбників](https://www.ukrinform.ua/rubric-ato/3703928-zsu-likviduvali-vze-191-940-rosijskih-zagarbnikiv.html) |
| `2023-05-03` | `p0` | `regions` | `0` | `0` | `0` | [Загарбники за добу атакували 11 регіонів України - зведення ОВА](https://www.ukrinform.ua/rubric-regions/3704026-armia-rf-za-dobu-atakuvala-11-regioniv-ukraini-zvedenna-ova.html) |
| `2023-05-04` | `p0` | `polytics` | `0` | `0` | `0` | [Зеленський і Рютте закликали росію негайно припинити війну](https://www.ukrinform.ua/rubric-polytics/3704829-zelenskij-i-rutte-zaklikali-rosiu-negajno-pripiniti-vijnu.html) |

## Sample: pk_ato

| Date | Period | Rubric | sc | oc | noc | Title |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `2023-05-01` | `p0` | `ato` | `0` | `0` | `0` | [ЗСУ за добу відбили понад 36 атак противника на трьох напрямках](https://www.ukrinform.ua/rubric-ato/3702924-zsu-za-dobu-vidbili-ponad-36-atak-protivnika-na-troh-napramkah.html) |
| `2023-05-01` | `p0` | `ato` | `0` | `0` | `0` | [ЗСУ знищили вже 190 960 російських загарбників](https://www.ukrinform.ua/rubric-ato/3702941-zsu-znisili-vze-190-960-rosijskih-zagarbnikiv.html) |
| `2023-05-01` | `p0` | `ato` | `0` | `0` | `0` | [Виплати 30 тисяч військовим: петиція до Президента набрала необхідну кількість голосів](https://www.ukrinform.ua/rubric-ato/3703077-viplati-30-tisac-vijskovim-peticia-do-prezidenta-nabrala-neobhidnu-kilkist-golosiv.html) |
| `2023-05-01` | `p0` | `ato` | `0` | `0` | `0` | [Зеленський пропонує Раді продовжити воєнний стан та загальну мобілізацію](https://www.ukrinform.ua/rubric-ato/3703348-zelenskij-proponue-radi-prodovziti-voennij-stan-ta-zagalnu-mobilizaciu.html) |
| `2023-05-02` | `p0` | `ato` | `0` | `0` | `0` | [Укази Президента про продовження воєнного стану та мобілізації пройшли комітет Ради](https://www.ukrinform.ua/rubric-ato/3703502-ukazi-prezidenta-pro-prodovzenna-voennogo-stanu-ta-mobilizacii-projsli-komitet-radi.html) |
| `2023-05-02` | `p0` | `ato` | `1` | `1` | `0` | [Рада продовжила воєнний стан та загальну мобілізацію ще на 90 діб](https://www.ukrinform.ua/rubric-ato/3703675-rada-prodovzila-voennij-stan-ta-zagalnu-mobilizaciu-se-na-90-dib.html) |
| `2023-05-02` | `p0` | `ato` | `0` | `0` | `0` | [Президент нагородив 63 військових](https://www.ukrinform.ua/rubric-ato/3703877-prezident-nagorodiv-63-vijskovih.html) |
| `2023-05-03` | `p0` | `ato` | `1` | `1` | `0` | [На Київщині зберігається повітряна небезпека - ОВА](https://www.ukrinform.ua/rubric-ato/3703896-na-kiivsini-zberigaetsa-povitrana-nebezpeka-ova.html) |

## Sample: pk_regions_sc0

| Date | Period | Rubric | sc | oc | noc | Title |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `2023-05-01` | `p0` | `regions` | `0` | `0` | `0` | [росіяни за добу атакували 11 областей України - зведення ОВА](https://www.ukrinform.ua/rubric-regions/3703012-rosiani-za-dobu-atakuvali-11-oblastej-ukraini-zvedenna-ova.html) |
| `2023-05-02` | `p0` | `regions` | `0` | `0` | `0` | [росіяни за добу обстріляли дев'ять областей України - зведення ОВА](https://www.ukrinform.ua/rubric-regions/3703575-rosiani-za-dobu-obstrilali-devat-oblastej-ukraini-zvedenna-ova.html) |
| `2023-05-03` | `p0` | `regions` | `0` | `0` | `0` | [Загарбники за добу атакували 11 регіонів України - зведення ОВА](https://www.ukrinform.ua/rubric-regions/3704026-armia-rf-za-dobu-atakuvala-11-regioniv-ukraini-zvedenna-ova.html) |
| `2023-05-04` | `p0` | `regions` | `0` | `0` | `0` | [росіяни за добу атакували десять областей України — зведення ОВА](https://www.ukrinform.ua/rubric-regions/3704553-rosiani-za-dobu-atakuvali-desat-oblastej-ukraini-zvedenna-ova.html) |
| `2023-05-04` | `p0` | `regions` | `0` | `0` | `0` | [Час комендантської години у Запоріжжі не зміниться - міськрада](https://www.ukrinform.ua/rubric-regions/3704895-cas-komendantskoi-godini-u-zaporizzi-ne-zminitsa-miskrada.html) |
| `2023-05-05` | `p0` | `regions` | `0` | `0` | `0` | [Ігор Табурець, начальник Черкаської ОВА](https://www.ukrinform.ua/rubric-regions/3705228-igor-taburec-nacalnik-cerkaskoi-ova.html) |
| `2023-05-06` | `p0` | `regions` | `0` | `0` | `0` | [росіяни за добу атакували дев'ять регіонів України - зведення ОВА](https://www.ukrinform.ua/rubric-regions/3705525-rosiani-za-dobu-atakuvali-devat-regioniv-ukraini-zvedenna-ova.html) |
| `2023-05-07` | `p0` | `regions` | `0` | `0` | `0` | [Війська рф за добу обстріляли дев’ять областей України - зведення ОВА](https://www.ukrinform.ua/rubric-regions/3705879-vijska-rf-za-dobu-obstrilali-devat-oblastej-ukraini-zvedenna-ova.html) |

## Sample: official_false_oc_gt0

| Date | Period | Rubric | sc | oc | noc | Title |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `2023-05-01` | `p0` | `ato` | `3` | `1` | `2` | [У Бахмуті загинув американський доброволець Купер Ендрюс](https://www.ukrinform.ua/rubric-ato/3702909-u-bahmuti-zaginuv-amerikanskij-dobrovolec-kuper-endrus.html) |
| `2023-05-01` | `p0` | `ato` | `4` | `2` | `2` | [росіяни атакували Україну зі стратегічної авіації, випустили 18 крилатих ракет - Залужний](https://www.ukrinform.ua/rubric-ato/3702927-rosiani-atakuvali-ukrainu-zi-strategicnoi-aviacii-vipustili-18-krilatih-raket-zaluznij.html) |
| `2023-05-01` | `p0` | `ato` | `2` | `1` | `1` | [путін не призначав командувача для вторгнення в Україну, щоб приписати «перемогу» собі – ISW](https://www.ukrinform.ua/rubric-ato/3703038-putin-ne-priznacav-komanduvaca-dla-vtorgnenna-v-ukrainu-sob-pripisati-peremogu-sobi-isw.html) |
| `2023-05-01` | `p0` | `ato` | `2` | `2` | `0` | [На Житомирщині під час нічної атаки є влучання у промисловий об’єкт](https://www.ukrinform.ua/rubric-ato/3703081-na-zitomirsini-pid-cas-nicnoi-ataki-e-vlucanna-u-promislovij-obekt.html) |
| `2023-05-01` | `p0` | `ato` | `7` | `2` | `3` | [Резніков вірить в успішність контрнаступу](https://www.ukrinform.ua/rubric-ato/3703119-reznikov-virit-v-uspisnist-kontrnastupu.html) |
| `2023-05-01` | `p0` | `ato` | `5` | `1` | `4` | [Із західних танків в Україні вже є «Леопарди» і «Челленджери» - Резніков](https://www.ukrinform.ua/rubric-ato/3703134-iz-zahidnih-tankiv-v-ukraini-vze-e-leopardi-i-cellendzeri-reznikov.html) |
| `2023-05-01` | `p0` | `ato` | `3` | `1` | `2` | [Резніков – про «снарядний голод»: Для контрнаступу підготовлений резерв](https://www.ukrinform.ua/rubric-ato/3703152-reznikov-pro-snaradnij-golod-dla-kontrnastupu-pidgotovlenij-rezerv.html) |
| `2023-05-01` | `p0` | `ato` | `6` | `2` | `3` | [Україна попросила у Японії засоби радіоелектронної боротьби з російськими дронами](https://www.ukrinform.ua/rubric-ato/3703164-ukraina-poprosila-u-aponii-zasobi-radioelektronnoi-borotbi-z-rosijskimi-dronami.html) |

## Sample: pk_minister_foreignish

| Date | Period | Rubric | sc | oc | noc | Title |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `2023-08-14` | `p0` | `polytics` | `0` | `0` | `0` | [Міністр фінансів Німеччини прибув до Києва](https://www.ukrinform.ua/rubric-polytics/3747976-ministr-finansiv-nimeccini-pribuv-do-kieva.html) |
| `2023-09-13` | `p0` | `polytics` | `1` | `1` | `0` | [Міністр закордонних справ Британії їде до Туреччини говорити про війну та зернову ініціативу](https://www.ukrinform.ua/rubric-polytics/3760594-ministr-zakordonnih-sprav-britanii-ide-do-tureccini-govoriti-pro-vijnu-ta-zernovu-iniciativu.html) |
| `2023-09-26` | `p0` | `ato` | `0` | `0` | `0` | [Міністр оборони Канади проінспектував навчання українських захисників у Британії](https://www.ukrinform.ua/rubric-ato/3766054-ministr-oboroni-kanadi-proinspektuvav-navcanna-ukrainskih-zahisnikiv-u-britanii.html) |
| `2023-09-28` | `p0` | `polytics` | `0` | `0` | `0` | [До Києва прибув міністр оборони Франції](https://www.ukrinform.ua/rubric-polytics/3767199-do-kieva-pribuv-ministr-oboroni-francii.html) |
| `2023-10-13` | `p0` | `polytics` | `0` | `0` | `0` | [Росія має заплатити за агресію: міністри фінансів G7 у Марокко підтримали Україну](https://www.ukrinform.ua/rubric-polytics/3773482-rosia-mae-zaplatiti-za-agresiu-ministri-finansiv-g7-u-marokko-pidtrimali-ukrainu.html) |
| `2023-10-29` | `p0` | `economy` | `0` | `0` | `0` | [Міністри G7 засудили війну Росії проти України і атаки на зернову інфраструктуру](https://www.ukrinform.ua/rubric-economy/3780019-ministri-g7-zasudili-vijnu-rosii-proti-ukraini-i-ataki-na-zernovu-infrastrukturu.html) |
| `2023-11-30` | `p1` | `polytics` | `0` | `0` | `0` | [На Раді міністрів ОБСЄ 36 країн закликали Росію негайно вивести війська з України](https://www.ukrinform.ua/rubric-polytics/3793929-na-radi-ministriv-obse-36-krain-zaklikali-rosiu-negajno-vivesti-vijska-z-ukraini.html) |
| `2023-11-30` | `p1` | `regions` | `1` | `1` | `0` | [СБУ повідомила про підозру ексбухгалтеру, який дослужився до «заступника міністра ЛНР»](https://www.ukrinform.ua/rubric-regions/3793711-sbu-ogolosila-pidozru-eksbuhgalteru-akij-dosluzivsa-do-zastupnika-ministra-lnr.html) |
