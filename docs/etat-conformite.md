# OmniChurch Connect — état de conformité au cahier des charges

**Comparaison section par section · 28 octobre 2026**
Version en ligne : https://omnichurch26.pythonanywhere.com

Légende : **FAIT** conforme et testé · **PARTIEL** une partie seulement · **À FAIRE** pas encore commencé

---

## 1. Mission et objectif — FAIT (cadre)
Le logiciel tourne réellement, avec base de données persistante, et se développe par phases successives. Aucune maquette statique.

## 2. Identité du produit — FAIT
Nom, bilinguisme français/anglais, multi-Églises. Chaque Église configure son nom, son adresse, sa dénomination, son année de fondation, son logo, ses deux couleurs et sa langue (endpoint `eglise/parametres/`). Église de référence créée : Église Lumière du Monde — Temple de Positionnement.

## 3. Architecture technique — PARTIEL
Django 5, SQLite persistant, admin maison en HTML rendu serveur, API JSON. Adaptation documentée par rapport à React/PostgreSQL imposés par le cahier des charges. Manquent encore : stockage objet privé pour les documents, environnement de test séparé, sauvegardes automatiques, PWA.

## 4. Architecture multi-Églises — FAIT
Chaque table porte la clé de l'Église ; toutes les lectures et écritures filtrent sur l'Église de l'utilisateur, vérifiée côté serveur. Le super-administrateur ne voit que des compteurs agrégés, jamais les données d'une Église. Église suspendue testée : connexion refusée, données intactes.

## 5. Administration générale — PARTIEL
**5.1 Super-administrateur** : existe, liste et valide les Églises, voit les inscriptions à compléter. Manquent : forfaits, abonnements, paiements, incidents.
**5.2 Inscription des Églises** : complète (nom, pays, ville, responsable, e-mail, téléphone), avec statuts en attente, à compléter, approuvé, refusé, motif et notification.
**5.3 Administration principale** : l'administrateur principal gère ses utilisateurs, ses rôles et ses permissions ; les délégations temporaires ont une date de fin et sont révocables immédiatement.

## 6. Utilisateurs, authentification et permissions — PARTIEL (l'essentiel est là)
Fait : connexion par e-mail et mot de passe, verrouillage après 5 échecs, sessions par appareil avec expiration et révocation, invitations individuelles à usage unique, rôles multiples par utilisateur, permissions par module et par action vérifiées côté serveur, journalisation des actions, suspension d'utilisateur.
Manque : authentification à deux facteurs (obligatoire pour l'administrateur principal selon la section 6), récupération de mot de passe autonome, vérification des nouveaux appareils, alertes de connexion suspecte, double validation par deux personnes pour les opérations critiques.

## 7. Tableau de bord — PARTIEL
Affiche utilisateurs actifs, invitations en attente, rôles, statut de l'essai et les huit dernières opérations du journal. Les blocs membres, finances, présences et événements attendent leurs modules.

## 8. Module des membres — À FAIRE (Phase 2)
Dossier individuel, matricules configurables, effectif global déclaré, workflow de validation, détection des doublons, historique des départs. Le module est déclaré dans les permissions mais aucune table n'existe encore.

## 9. Documents des membres — À FAIRE

## 10. Module financier — À FAIRE (Phase 4)

## 11. Groupes et départements — À FAIRE

## 12. Présences — À FAIRE

## 13. Calendrier et événements — À FAIRE

## 14. Intervenants et bibliothèque média — À FAIRE

## 15. Enfants et école du dimanche — À FAIRE

## 16. Suivi pastoral — À FAIRE

## 17. Gestion des documents — À FAIRE

## 18. Patrimoine et équipements — À FAIRE

## 19. Gestion des enfants — À FAIRE (détaillée en section 15)

## 20. Communication et notifications — À FAIRE

## 21. Rapports et statistiques — À FAIRE

## 22. Site public de chaque Église — PARTIEL
Une page publique d'accueil, d'inscription et de connexion existe. Le site public personnalisable par Église, avec horaires, annonces, agenda et formulaires, reste à construire.

## 23. Dons en ligne — À FAIRE (Phase 6)

## 24. Portail personnel des membres — À FAIRE (Phase 5)

## 25. Abonnements et plateforme — PARTIEL
Essai gratuit de sept jours avec date d'expiration, suspension et réactivation sans perte de données, supervision des Églises par le super-administrateur. Manquent : grille tarifaire, paiements, rappels avant expiration, historique des paiements.

## 26. Sécurité, sauvegarde et restauration — PARTIEL
Fait : isolation, contrôle des permissions serveur, verrouillage des comptes, journal d'audit accessible et non modifiable par les utilisateurs ordinaires, sessions révocables. Manquent : 2FA, sauvegardes chiffrées, tests de restauration, procédure de reprise documentée.

## 27. Multilingue et personnalisation — PARTIEL
Interface d'administration en français et en anglais, langue choisie par Église, logo et couleurs par Église. Manquent : fuseau horaire et formats de date/heure par Église, choix de langue et de thème par utilisateur.

## 28. Interface et expérience — FAIT pour le périmètre actuel
Interface institutionnelle bleu nuit et or, responsive, menus adaptés aux permissions, messages d'erreur explicites. PWA non installable à ce stade.

## 29. Fonctionnement hors ligne — À FAIRE

## 30. Architecture et base de données — PARTIEL
7 tables de fondation livrées : Église, Utilisateur, Session, Rôle, Rôle utilisateur, Invitation, Journal d'audit. Les 17 autres entités du cahier des charges restent à créer avec leurs modules.

## 31. Tests et critères d'acceptation — PARTIEL
Testé manuellement et vérifié en ligne : inscription d'une Église, connexion, verrouillage après échecs, attribution et retrait de permissions, révocation de session, isolation entre deux Églises, suspension et réactivation. Manque : suite de tests automatisés à chaque livraison.

## 32. Développement progressif — Phase 1 terminée
Les phases 2 à 7 restent à exécuter dans l'ordre prévu.

## 33. Livrables — PARTIEL
Code source, schéma de base, scripts de migration, système d'authentification, permissions, API et interfaces existent. Manquent : documentation technique, guides d'installation et d'administration, procédures de sauvegarde et de restauration.

## 34. Instructions finales — respecté
La Phase 1 a été construite d'abord, sans démonstration fictive, avec des choix techniques documentés.

---

## Ce que la Phase 2 doit livrer

1. Table des membres et dossier individuel complet.
2. Matricules configurables, attribués après validation du dossier, uniques et jamais réutilisés.
3. Effectif global déclaré, additif, avec versions successives et avertissement de chevauchement.
4. Workflow de validation : approuver, retourner, rejeter avec motif.
5. Détection des doublons sans fusion automatique.
6. Groupes et départements, avec responsabilités et mandats.
7. Présences, y compris visiteurs et effectifs globaux.
8. Documents de base : fiche administrative PDF et carte de membre.
9. Tableau de bord complété avec les effectifs réels.

## Trois manques de sécurité à traiter avant toute mise en service réelle

1. Authentification à deux facteurs pour l'administrateur principal, exigée par la section 6.
2. Double validation par deux personnes distinctes pour les décaissements et les documents officiels.
3. Sauvegardes chiffrées avec test de restauration, et non de simples copies.

---

*État de conformité OmniChurch Connect · 28 octobre 2026 · Inspire by YuuStore*
