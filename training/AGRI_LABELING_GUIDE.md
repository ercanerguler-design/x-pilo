# Tarim Etiketleme Rehberi

Bu rehber, karpuz tarlasi senaryosunda YOLO veri seti etiket standardini tanimlar.

## Siniflar

- `0 karpuz`: korunacak urun.
- `1 kaktus`: mudahale adayi zararli bitki.
- `2 ot`: zararli yabanci ot.
- `3 belirsiz`: modelin kararsiz kalabilecegi hedefler.

## Etiketleme Kurallari

- Bounding box hedefin tamamini kapsar, tasmaz.
- Karpuz meyvesi yerine bitkinin gorsel govdesi etiketlenir.
- Ayni hedef iki farkli sinifla etiketlenmez.
- Belirsiz sinifi sadece net ayrim yapilamayan durumlarda kullanilir.

## Guvenlik Kurali

Backend hard-rule geregi `belirsiz` hedefler otomatik mudahaleye kapatilir.
Bu sinifin dogru kullanimi sahadaki yanlis mudahaleyi dogrudan azaltir.
