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

## 7. Tableau de bord — FAIT (périmètre actuel)
Affiche les membres enregistrés, les dossiers à valider, le total général déclaré, les groupes actifs, les présences pointées, les utilisateurs, les invitations et les dernières opérations du journal. Les blocs finances et événements complets viendront avec leurs modules.

## 8. Module des membres — FAIT (Phase 2)
Dossier individuel complet (identité, coordonnées, adhésion, ordination, observations), matricule configurable attribué uniquement à la validation, workflow approuver / retourner / rejeter avec motif, détection des doublons sans fusion automatique, archivage sans perte du dossier ni du matricule, recherche, filtres et pagination.
Règle de l'effectif global déclaré implémentée : total général = dossiers individuels + effectifs déclarés, avec versions successives, auteur, période et avertissement de double comptage.

## 9. Documents des membres — PARTIEL
Fiche administrative PDF avec l'identité visuelle de l'Église, et carte de membre imprimable délivrée après attribution du matricule. Manquent : certificats et attestations, numérotation officielle, QR de vérification, impression par lots.

## 10. Module financier — À FAIRE (Phase 4)

## 11. Groupes et départements — FAIT (Phase 2)
Groupes de type libre (département, ministère, cellule, chorale, équipe, jeunesse), hiérarchie parent, responsable désigné, affectation d'un membre avec sa fonction, refus des doubles appartenances, effectif du groupe calculé, retrait daté et désactivation sans suppression.

## 12. Présences — FAIT (Phase 2, sans mode hors ligne)
Pointage par membre, par visiteur non enregistré ou par effectif global déclaré, sans doublon possible sur une même personne et une même activité, retards, suppression contrôlée, statistiques par activité. Reste à faire : QR code, saisie hors connexion avec synchronisation.

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

## 30. Architecture et base de données — PARTIEL (13 tables)
Tables livrées : Église, Utilisateur, Session, Rôle, Rôle utilisateur, Invitation, Journal d'audit, Membre, Paramètre de matricule, Effectif déclaré, Groupe, Appartenance au groupe, Activité pointée, Présence. Les entités financières, documentaires, pastorales et patrimoniales restent à créer avec leurs modules.

## 31. Tests et critères d'acceptation — PARTIEL (39 vérifications automatisées en Phase 2)
Suite de tests rejouable (test_phase2.py) couvrant : création et validation de dossier, attribution du matricule, non-réutilisation, doublons, retour et rejet, règle additive des effectifs, groupes et doubles appartenances, pointage unique, visiteurs et effectif global, permissions refusées au rôle lecture seule, isolation entre deux Églises sur six scénarios, génération des PDF, export CSV, alimentation du tableau de bord et présence de chaque action dans le journal d'audit. 39 sur 39 réussies. Manquent : tests de charge et tests de restauration.

## 32. Développement progressif — Phase 1 terminée
Les phases 2 à 7 restent à exécuter dans l'ordre prévu.

## 33. Livrables — PARTIEL
Code source, schéma de base, scripts de migration, système d'authentification, permissions, API et interfaces existent. Manquent : documentation technique, guides d'installation et d'administration, procédures de sauvegarde et de restauration.

## 34. Instructions finales — respecté
La Phase 1 a été construite d'abord, sans démonstration fictive, avec des choix techniques documentés.

---

## Phase 2 livrée le 28 octobre 2026

Membres et dossiers individuels, matricules configurables, effectif global déclaré, workflow de validation, détection des doublons, groupes et départements, présences avec visiteurs et effectifs globaux, fiche et carte en PDF, export CSV, tableau de bord alimenté. 39 vérifications automatisées réussies.

## Ce que la Phase 3 doit livrer

1. Calendrier complet : cultes, réunions, veillées, séminaires, récurrentes, rappels, changement d'horaire.
2. Gestion des salles et des équipements avec détection des conflits.
3. Inscriptions aux événements : capacités, liste d'attente, frais, pointage par QR code.
4. Intervenants : répertoire, coordonnées protégées, disponibilités, historique des interventions.
5. Bibliothèque média : prédications, enseignements, séries, playlists, fichiers et liens.
6. Communications internes : annonces, messages ciblés par groupe, modèles et historique.

## Trois manques de sécurité à traiter avant toute mise en service réelle

1. Authentification à deux facteurs pour l'administrateur principal, exigée par la section 6.
2. Double validation par deux personnes distinctes pour les décaissements et les documents officiels.
3. Sauvegardes chiffrées avec test de restauration, et non de simples copies.

---

*État de conformité OmniChurch Connect · 28 octobre 2026 · Inspire by YuuStore*
