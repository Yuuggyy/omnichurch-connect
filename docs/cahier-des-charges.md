# OMNICHURCH CONNECT

## Spécification générale de conception et de développement

**Plateforme intégrée de gestion des Églises**
Version validée — document de référence, 34 sections.

---

## 1. MISSION ET OBJECTIF

Tu es une équipe expérimentée composée d'architectes logiciels, de développeurs full-stack, d'experts en bases de données, de spécialistes en cybersécurité, de concepteurs UX/UI et de responsables qualité.

Ta mission est de concevoir et de développer OmniChurch Connect, une plateforme professionnelle, sécurisée, multilingue et multi-Églises permettant de gérer l'ensemble des activités administratives, spirituelles, financières, organisationnelles et publiques des Églises.

Le résultat attendu est un véritable logiciel fonctionnel, connecté à une base de données persistante, et non une simple maquette graphique, une démonstration statique ou une interface contenant des données fictives.

Le développement doit suivre une architecture évolutive et une méthode progressive. Les fonctionnalités déjà développées doivent rester opérationnelles à mesure que de nouveaux modules sont ajoutés.

Ne te limite pas à expliquer ce qu'il faudrait faire : construis effectivement les éléments que ton environnement permet de développer, de tester et de livrer.

## 2. IDENTITÉ DU PRODUIT

Nom officiel : OmniChurch Connect.

Langues initiales : français et anglais.

Positionnement : plateforme institutionnelle premium destinée aux Églises, ministères, communautés chrétiennes et organisations ecclésiastiques indépendantes.

Organisation de référence : Église Lumière du Monde — Temple de Positionnement. Cette organisation sert de référence fonctionnelle, mais ne doit pas être imposée comme seule Église utilisatrice.

Chaque Église doit pouvoir configurer son nom, son logo, ses couleurs, ses coordonnées, ses responsables, ses règles internes et ses paramètres, sans modifier l'environnement des autres Églises.

L'interface doit être élégante, professionnelle, claire, moderne, rapide et facile à prendre en main.

## 3. ARCHITECTURE TECHNIQUE

Conçois une architecture moderne, maintenable et adaptée à une plateforme multi-tenant.

Stack technique de référence, à adapter aux capacités réelles du générateur :

- Frontend : React avec TypeScript et un système de composants réutilisables.
- Interface : bibliothèque de composants accessible, formulaires validés, tableaux filtrables, graphiques et navigation responsive.
- Backend : API sécurisée avec validation serveur et logique métier centralisée.
- Base de données : PostgreSQL ou une base relationnelle équivalente adaptée aux transactions et aux relations entre entités.
- Authentification : fournisseur sécurisé ou service backend dédié, avec gestion des sessions, récupération de compte et authentification à deux facteurs.
- Stockage documentaire : stockage objet privé, avec contrôle d'accès, versions et liens temporaires lorsque nécessaire.
- Application installable : PWA avec cache maîtrisé et synchronisation sélective.
- Déploiement : environnement de développement, de test et de production distincts.
- Sauvegardes : stockage indépendant du serveur principal, avec chiffrement et tests de restauration.

Si le générateur impose une autre technologie, conserve les mêmes propriétés fonctionnelles et de sécurité. Documente les adaptations et leurs conséquences.

Sépare clairement la présentation, la logique métier, les règles d'autorisation, les accès aux données et les intégrations externes.

Ne place jamais les secrets, clés privées, mots de passe techniques ou clés d'administration dans le code frontend.

Toute fonctionnalité doit être reliée à son véritable mécanisme de persistance. Ne simule pas une sauvegarde, un paiement, une authentification, une notification ou une validation en affichant simplement un message de succès.

## 4. ARCHITECTURE MULTI-ÉGLISES

La plateforme doit permettre à plusieurs Églises indépendantes de partager le même service sans partager leurs données privées.

Chaque Église dispose de son propre espace institutionnel, de ses utilisateurs, membres, groupes, finances, documents, activités, paramètres, abonnements et historiques.

Implémente une isolation stricte des données au niveau du serveur et de la base de données.

Exigences obligatoires :

- Toute donnée appartenant à une Église doit être rattachée à son identifiant institutionnel.
- L'appartenance de l'utilisateur à l'Église concernée doit être vérifiée côté serveur à chaque opération.
- Les identifiants fournis par le navigateur ne doivent jamais suffire à autoriser l'accès à une organisation.
- Les recherches, exports, fichiers, notifications, rapports et requêtes doivent respecter la même isolation.
- Les relations entre enregistrements doivent empêcher les références à des données appartenant à une autre Église.
- Les tests doivent vérifier qu'un utilisateur ne peut ni consulter ni modifier les données d'une autre organisation en changeant une URL, un identifiant ou une requête API.
- Chaque Église doit pouvoir être suspendue ou réactivée sans supprimer ses données.
- Prévoir la possibilité de restaurer les données d'une seule Église lorsque l'architecture le permet.

## 5. ADMINISTRATION GÉNÉRALE ET ADMINISTRATION DES ÉGLISES

### 5.1 Super-administrateur général

Créer un rôle unique de super-administrateur général chargé de gérer :

- Les Églises inscrites et leur statut de validation.
- Les forfaits, abonnements et limites d'utilisation.
- Les paiements des abonnements et les paramètres commerciaux.
- Les incidents techniques et la supervision de la plateforme.
- Les paramètres globaux, les intégrations, les mises à jour et les audits.
- Les sauvegardes et les procédures de reprise.

Le super-administrateur ne doit pas bénéficier d'un accès permanent et injustifié aux données confidentielles des Églises.

Tout accès technique exceptionnel à des données privées doit être justifié, temporaire, limité à un périmètre précis et intégralement journalisé.

### 5.2 Inscription des Églises

Créer un parcours d'inscription comprenant au minimum :

- Nom de l'Église.
- Pays et ville.
- Nom du responsable principal.
- Adresse e-mail.
- Numéro de téléphone.

Permettre ensuite de compléter les informations institutionnelles, l'adresse, la dénomination, l'année de fondation, les responsables et les documents justificatifs éventuels.

Détecter les inscriptions potentiellement dupliquées, sans fusion automatique.

Après création validée de l'espace, le premier responsable autorisé devient administrateur principal. L'inscription ne vaut pas certification officielle de l'organisation.

Prévoir les statuts en attente, à compléter, approuvé et refusé, avec motifs et notifications.

### 5.3 Administration principale de chaque Église

L'administrateur principal peut gérer les paramètres de son Église, les utilisateurs, les rôles, les permissions et les règles de validation.

Il peut désigner des administrateurs délégués permanents ou temporaires, avec des droits précisément définis, des dates de validité, un historique et une possibilité de révocation immédiate.

Les délégués ne peuvent ni augmenter eux-mêmes leurs permissions ni créer librement de nouveaux comptes.

## 6. UTILISATEURS, AUTHENTIFICATION ET PERMISSIONS

Prévoir la connexion par adresse e-mail, identifiant ou numéro de téléphone vérifié, avec mot de passe.

Inclure :

- Récupération sécurisée des comptes.
- Vérification des nouveaux appareils.
- Authentification à deux facteurs obligatoire pour l'administrateur principal et les utilisateurs disposant de droits sensibles.
- Protection contre les tentatives répétées de connexion.
- Alertes de connexion suspecte.
- Consultation et révocation des sessions et appareils.
- Invitations individuelles à usage unique et à expiration.
- Gestion des utilisateurs actifs, suspendus et révoqués.
- Procédures de récupération assistée sans révéler les mots de passe.
- Journalisation des actions administratives.

Seul l'administrateur principal peut créer des utilisateurs manuellement ou leur envoyer des invitations autorisées.

Les permissions doivent pouvoir être configurées par module et par action : consulter, créer, modifier, valider, rejeter, archiver, supprimer, imprimer et exporter.

Prévoir des rôles prédéfinis, des rôles personnalisés, plusieurs rôles par utilisateur et des permissions temporaires.

Les droits doivent être vérifiés côté serveur. Masquer un bouton dans l'interface ne constitue pas une mesure d'autorisation suffisante.

Certaines opérations critiques doivent pouvoir exiger deux validations par deux personnes distinctes : décaissements sensibles, clôtures financières, suppressions définitives, restaurations, délégations privilégiées et délivrance de documents officiels lorsque les règles l'imposent.

L'auteur d'une opération ne peut pas être son unique approbateur lorsque la double validation est requise.

## 7. TABLEAU DE BORD

Créer un tableau de bord personnalisable selon les rôles et les permissions.

Afficher, selon les droits :

- Nombre de membres enregistrés et effectif global déclaré.
- Nouvelles adhésions et demandes d'intégration.
- Présences aux cultes et activités.
- Répartition des groupes et départements.
- Recettes, dépenses, soldes et budgets.
- Projets en cours.
- Événements à venir.
- Activités des enfants et de l'école du dimanche.
- Tâches en retard.
- Documents et demandes en attente.
- Indicateurs de suivi pastoral autorisés.
- Alertes administratives, financières et techniques.

Les montants en USD et CDF doivent être présentés séparément, sauf conversion explicite au moyen d'un taux documenté.

Les informations sensibles ne doivent jamais apparaître sur un tableau de bord auquel l'utilisateur n'a pas droit.

## 8. MODULE DES MEMBRES

Créer un dossier individuel comprenant notamment :

- Nom, postnom et prénom.
- Sexe.
- Date et lieu de naissance.
- Nationalité.
- Profession.
- État civil.
- Coordonnées.
- Adresse.
- Personne à contacter.
- Date d'adhésion.
- Date d'ordination, si applicable.
- Statut, groupe et responsabilités.
- Photo facultative.
- Documents associés et observations soumises aux permissions appropriées.

Les champs obligatoires doivent être configurables, avec un profil initial comprenant les informations essentielles définies par l'Église.

Prévoir des statuts personnalisables, avec des valeurs initiales telles que actif, visiteur, nouveau venu, en intégration, transféré, suspendu et décédé.

Le statut d'un membre ne doit pas être confondu avec ses fonctions ou responsabilités.

### Matricules

Permettre de configurer le préfixe, l'année, le nombre de chiffres et le format du matricule.

Exemple : ELM-2026-0001.

Le matricule officiel est attribué uniquement après approbation du dossier. Il est unique par Église et n'est jamais réutilisé.

### Effectif global déclaré

Distinguer :

1. Les membres disposant d'un dossier individuel.
2. L'effectif global déclaré des personnes non enregistrées individuellement dans la catégorie concernée.

Appliquer la règle fonctionnelle suivante :

Total général déclaré = effectif global déclaré + membres enregistrés.

Conserver les versions successives des effectifs déclarés, la période, l'auteur, la date et les observations. La fréquence de mise à jour est configurable.

Cette règle additive doit être clairement documentée, et les rapports doivent avertir l'utilisateur du risque de chevauchement entre catégories afin d'éviter toute interprétation trompeuse.

### Validation et doublons

Créer un workflow de validation des dossiers avec possibilité d'approuver, de retourner pour correction ou de rejeter avec motif.

Détecter les doublons potentiels à partir des noms, téléphones, e-mails, dates de naissance et matricules.

Ne jamais fusionner automatiquement deux personnes sur la seule base d'une similarité. Toute fusion doit être autorisée, contrôlée et traçable.

### Historique et départs

Conserver l'historique des modifications, changements de statut, transferts, départs, réactivations et archivages.

Une sortie ne doit pas entraîner automatiquement la suppression du dossier ni des documents associés.

## 9. DOCUMENTS DES MEMBRES

Permettre la production de :

- Fiches administratives PDF.
- Fiches complètes réservées aux utilisateurs autorisés.
- Cartes de membre.
- Certificats et attestations.
- Formulaires vierges imprimables.
- Archives personnelles.
- Documents numérisés.

Prévoir les certificats de baptême, mariage, ordination, consécration, transfert, formation et service, ainsi que les catégories personnalisées.

Chaque document officiel doit pouvoir recevoir un numéro unique, une date de délivrance, un statut et un historique de réédition.

Prévoir des QR codes de vérification n'exposant que les informations strictement nécessaires.

Permettre l'impression individuelle et par lots, avec le logo et les informations de l'Église.

Les documents officiels soumis à approbation ne doivent pas être délivrés définitivement avant validation.

## 10. MODULE FINANCIER

Construire un véritable module financier transactionnel.

### 10.1 Recettes

Gérer les dîmes, offrandes, dons, contributions spéciales, cotisations, événements, projets, constructions, évangélisation, œuvres sociales et catégories personnalisées.

Prendre en charge :

- Contributions individuelles.
- Collectes globales.
- Dons anonymes.
- Contributions de visiteurs non membres.
- Justificatifs et pièces jointes.
- Reçus numérotés après confirmation de l'opération.

Ne pas attribuer artificiellement une collecte globale aux membres individuellement.

### 10.2 Comptes et caisses

Gérer plusieurs comptes et caisses :

- Espèces USD et CDF.
- Comptes bancaires.
- M-Pesa.
- Airtel Money.
- Orange Money.
- Autres comptes configurables.

Chaque compte possède sa devise, son solde, son historique et ses permissions.

Les transferts internes ne sont ni des recettes ni des dépenses. Les frais de transfert sont enregistrés séparément.

### 10.3 Dépenses et validations

Gérer les dépenses courantes, engagements, avances, remboursements, indemnités, rémunérations et prêts.

Prévoir les états demandé, à vérifier, approuvé, rejeté, payé, clôturé ou annulé.

L'approbation d'une dépense ne signifie pas qu'elle a été payée.

Les seuils d'approbation sont configurables par montant, catégorie, compte et département. Les opérations sensibles peuvent exiger une double validation.

Exiger un justificatif ou une explication documentée, selon la politique définie. Signaler les pièces manquantes et les exceptions.

### 10.4 Devises

Gérer séparément USD et CDF.

Enregistrer pour chaque conversion le taux appliqué, la date, la source et, le cas échéant, l'utilisateur ayant effectué la saisie manuelle.

Les taux historiques ne doivent jamais être modifiés automatiquement lorsque le taux courant change.

### 10.5 Budgets et projets

Créer des budgets par département, activité et projet.

Suivre les montants approuvés, engagés, payés, restants et les écarts. Déclencher des alertes configurables, par exemple à 75 %, 90 % et 100 % de consommation.

Par défaut, bloquer les dépassements non autorisés.

Pour chaque projet, suivre les contributions promises et reçues, les dépenses, les justificatifs, les objectifs, le budget, le solde et l'état d'avancement.

### 10.6 Clôtures et rapprochements

Prévoir les rapprochements de caisse, de banque et de Mobile Money lorsque les relevés sont disponibles.

Signaler les écarts et exiger leur justification.

Mettre en place une clôture mensuelle avec contrôles, séparation entre préparation et approbation, verrouillage des périodes clôturées et corrections auditées.

Produire des rapports financiers annuels en PDF et Excel, avec soldes d'ouverture et de clôture, recettes, dépenses, budgets, projets, écarts, justificatifs manquants et validations.

Aucun rapprochement ou rapport ne doit créer artificiellement des transactions comptables supplémentaires.

## 11. GROUPES, DÉPARTEMENTS ET MINISTÈRES

Permettre de créer des structures personnalisées : départements, ministères, cellules, chorales, équipes, groupes de prière, groupes de jeunes et autres.

Configurer leur hiérarchie et leurs responsabilités.

Gérer les responsables, adjoints, secrétaires, trésoriers, membres, mandats et dates de nomination.

Un membre peut appartenir à plusieurs groupes.

Les responsabilités de trésorier d'un groupe ne donnent pas automatiquement accès à l'ensemble des finances de l'Église.

Relier chaque groupe aux réunions, présences, activités, tâches, objectifs, documents, rapports et budgets autorisés.

## 12. PRÉSENCES

Enregistrer les présences par recherche du membre, liste numérique, QR code individuel ou saisie manuelle.

Prendre en charge les visiteurs sans dossier individuel, les retards et les effectifs globaux déclarés.

Éviter les doublons de pointage.

Pour les effectifs globaux, calculer les absences globales selon la règle définie sans attribuer individuellement une absence à une personne non identifiée.

Permettre la saisie hors connexion lorsque cela est compatible, avec synchronisation, détection des conflits et historique des corrections.

Produire des statistiques et rapports par événement, groupe, département, période et catégorie.

## 13. CALENDRIER, CULTES ET ÉVÉNEMENTS

Créer un calendrier pour les cultes, réunions, prières, veillées, conférences, séminaires, retraites, formations, évangélisations, baptêmes, mariages, funérailles et autres activités.

Prévoir les événements récurrents, les responsables, les intervenants, les horaires, les lieux, les programmes détaillés, les rappels et les changements d'horaire.

Permettre de distinguer les notes internes du contenu public.

Gérer les inscriptions, capacités, listes d'attente, frais éventuels et pointages à l'aide de QR codes ou de listes manuelles.

Les déclarations de paiement d'inscription ne doivent pas être considérées comme encaissées avant vérification.

Ajouter la gestion des salles, bâtiments, équipements, réservations, conflits de calendrier, tâches logistiques, fournisseurs et bilans après événement.

Relier les dépenses à la comptabilité centrale sans créer de doublons.

## 14. INTERVENANTS ET BIBLIOTHÈQUE MÉDIA

Créer un répertoire d'intervenants : pasteurs, évangélistes, prophètes, chanteurs, formateurs et autres orateurs.

Gérer leurs coordonnées protégées, organisations, disponibilités, invitations, documents et interventions précédentes.

Relier les intervenants à leurs dossiers membres lorsqu'ils existent, sans créer de doublons.

Créer une bibliothèque audio et vidéo pour les prédications, enseignements, chants et conférences.

Gérer les titres, dates, intervenants, thèmes, séries, références bibliques, playlists, fichiers, liens externes et transcriptions lorsqu'un service compatible est disponible.

Prévoir une bibliothèque documentaire pour les études bibliques, plans de lecture, manuels, brochures, programmes de prière et ressources téléchargeables.

Respecter les droits d'auteur, les licences et les autorisations de diffusion.

## 15. ENFANTS ET ÉCOLE DU DIMANCHE

Créer des dossiers distincts et hautement protégés pour les enfants.

Gérer les parents et tuteurs autorisés, contacts d'urgence, classes par âge, moniteurs, leçons, activités, présences et progression pédagogique.

Prévoir un contrôle des arrivées et départs, la vérification des personnes autorisées à récupérer chaque enfant, les incidents et les autorisations parentales.

Les informations de santé ou de besoins particuliers ne doivent être recueillies que si elles sont nécessaires et leur accès doit être strictement limité.

Les communications adressées aux parents doivent respecter les autorisations.

Les statistiques, exports, documents et historiques doivent être protégés par des permissions spécifiques.

## 16. SUIVI PASTORAL ET ACCOMPAGNEMENT

Le logiciel doit intégrer un module complet permettant d'organiser, de suivre et d'évaluer l'accompagnement pastoral des membres et des personnes en contact avec l'Église.

### 16.1 Fonctionnalités principales

- Gestion des visites pastorales.
- Gestion des rendez-vous avec les pasteurs et responsables.
- Enregistrement des demandes de prière.
- Suivi des nouveaux convertis.
- Suivi des personnes en cours d'intégration.
- Accompagnement des familles.
- Suivi des personnes en difficulté.
- Organisation des actions de réintégration des membres éloignés.
- Gestion des visites à domicile, à l'hôpital et dans d'autres lieux.
- Attribution de chaque dossier à un pasteur ou à un responsable autorisé.

Gérer les visites, rendez-vous, nouveaux convertis, demandes de prière, intégration, accompagnement familial et suivi des personnes éloignées des activités. Planifier les rencontres, actions, objectifs, rappels et étapes de suivi.

### 16.2 Gestion des dossiers

Chaque dossier doit pouvoir contenir :

- La personne concernée.
- La nature de la demande.
- La date de création.
- Le responsable chargé du suivi.
- Les rendez-vous programmés.
- Les actions réalisées.
- Les prochaines étapes.
- Les rappels et échéances.
- L'état d'avancement du dossier.
- Les documents associés.

### 16.3 Confidentialité

Les notes pastorales doivent être protégées par des autorisations spécifiques. Elles ne doivent jamais apparaître dans les documents administratifs ordinaires d'un membre. Séparer les notes pastorales confidentielles des données administratives.

Chaque consultation ou modification d'un dossier confidentiel doit être enregistrée dans le journal d'audit.

## 17. GESTION DES DOCUMENTS

Le logiciel doit centraliser les documents administratifs et institutionnels de chaque Église.

### 17.1 Documents pris en charge

- Fiches des membres.
- Cartes de membre.
- Certificats de baptême.
- Certificats de mariage.
- Attestations d'ordination.
- Certificats de consécration.
- Attestations de transfert.
- Attestations de formation.
- Documents administratifs internes.
- Formulaires vierges.
- Rapports et procès-verbaux.
- Documents relatifs aux activités et aux projets.

### 17.2 Gestion documentaire

Le système doit permettre :

- Le classement par catégorie.
- La recherche par nom, date, numéro ou catégorie.
- L'archivage des fichiers PDF et des autres formats pris en charge.
- La gestion des versions.
- Le contrôle des droits d'accès.
- Le téléchargement et l'impression.
- La génération de documents à partir de modèles.
- L'enregistrement de l'auteur et de la date de création.
- La gestion des dates d'expiration lorsque cela s'applique.
- L'envoi d'alertes avant expiration selon des délais configurables.

Les documents officiels doivent posséder une numérotation unique et un historique des rééditions.

## 18. PATRIMOINE ET ÉQUIPEMENTS

Le système doit permettre à chaque Église de connaître, localiser et suivre ses biens.

### 18.1 Biens concernés

- Terrains.
- Bâtiments.
- Salles et locaux.
- Chaises et tables.
- Instruments de musique.
- Matériel de sonorisation.
- Matériel audiovisuel.
- Ordinateurs et équipements informatiques.
- Véhicules.
- Groupes électrogènes.
- Matériel de bureau.
- Autres biens configurables.

### 18.2 Fiche de chaque bien

Chaque bien doit pouvoir disposer :

- D'un identifiant unique.
- D'une désignation.
- D'une catégorie.
- D'une photographie.
- D'une date d'acquisition.
- D'une valeur d'acquisition.
- D'une origine ou source d'acquisition.
- D'une localisation.
- D'un responsable.
- D'un état actuel.
- Des documents justificatifs.
- D'un historique des mouvements.
- D'un historique de maintenance.

### 18.3 Inventaire et maintenance

Le logiciel doit permettre de réaliser des inventaires périodiques, d'enregistrer les écarts constatés, de planifier les réparations et de conserver l'historique des interventions.

Les achats et dépenses liés aux biens doivent pouvoir être reliés au module financier sans créer de doublons comptables.

## 19. GESTION DES ENFANTS ET DE L'ÉCOLE DU DIMANCHE

Le système doit intégrer un espace spécialement conçu pour la gestion des enfants et des activités qui leur sont destinées.

### 19.1 Gestion des enfants

- Création d'une fiche individuelle.
- Identification des parents ou tuteurs.
- Coordonnées des personnes à contacter en cas d'urgence.
- Affectation à une classe ou à un groupe.
- Historique de présence.
- Informations utiles à l'encadrement.
- Gestion des autorisations parentales.
- Suivi des incidents éventuels.

### 19.2 Sécurité

Le système doit prévoir :

- L'enregistrement des personnes autorisées à récupérer un enfant.
- Le contrôle des entrées et sorties.
- Des autorisations d'accès strictes.
- La protection des informations personnelles.
- Un accès limité aux responsables habilités.
- L'historique des opérations sensibles.

Les données concernant les enfants doivent être limitées à ce qui est nécessaire à leur encadrement et à leur sécurité.

## 20. COMMUNICATION ET NOTIFICATIONS

Le logiciel doit permettre à l'administration de communiquer avec les membres, les responsables, les départements et les participants aux activités.

### 20.1 Fonctionnalités

- Notifications internes.
- Annonces générales.
- Messages ciblés par groupe ou département.
- Rappels de réunions et d'activités.
- Notifications de modification d'horaire.
- Rappels de rendez-vous.
- Communications relatives aux événements.
- Programmation des messages.
- Historique des communications.
- Gestion des modèles de messages.

### 20.2 Canaux de communication

Selon les intégrations réellement disponibles, le système pourra prendre en charge :

- Les notifications dans l'application.
- Le courrier électronique.
- Les SMS.
- WhatsApp.

Le logiciel ne doit jamais déclarer un message livré ou lu sans confirmation fournie par le service concerné.

## 21. RAPPORTS ET STATISTIQUES

Le logiciel doit offrir un système de rapports adapté aux différents niveaux de responsabilité.

### 21.1 Rapports administratifs

- Effectif des membres.
- Répartition par sexe, âge, statut ou département.
- Nouveaux membres.
- Membres en cours d'intégration.
- Présences et absences.
- Évolution de l'effectif.
- Statistiques des activités.
- Rapports des départements.
- Documents générés.
- Historique des opérations administratives.

### 21.2 Rapports financiers

- Recettes par catégorie.
- Dépenses par catégorie.
- Situation des comptes et caisses.
- Suivi des budgets.
- Rapports par projet.
- Rapprochements financiers.
- Rapports mensuels et annuels.
- Situation des contributions.
- Rapports des collectes d'activités.

Les montants en USD et en CDF doivent rester distincts, sauf lorsqu'une conversion est explicitement affichée avec son taux, sa date et sa source.

### 21.3 Exportation

Les rapports doivent pouvoir être :

- Consultés à l'écran.
- Exportés en PDF.
- Exportés en Excel lorsque le format est pris en charge.
- Imprimés.
- Filtrés par période.
- Programmés pour une génération périodique.
- Consultés uniquement par les utilisateurs autorisés.

## 22. SITE INTERNET PUBLIC DE CHAQUE ÉGLISE

Chaque Église doit pouvoir disposer d'un espace public personnalisable, relié à son compte OmniChurch Connect.

### 22.1 Informations publiques

- Nom officiel de l'Église.
- Logo et identité visuelle.
- Présentation de l'Église.
- Adresse et coordonnées.
- Horaires des cultes.
- Calendrier public.
- Annonces et actualités.
- Affiches des événements.
- Prédications et enseignements autorisés.
- Ressources numériques.
- Liens vers les réseaux sociaux.
- Formulaire de contact.
- Formulaire de demande de prière.
- Formulaire d'intégration.

### 22.2 Administration du site

Les utilisateurs autorisés doivent pouvoir créer, modifier, programmer et publier des contenus.

Les brouillons, documents internes et informations confidentielles ne doivent jamais être publiés automatiquement.

Toute publication peut être soumise à un processus de validation avant sa mise en ligne.

## 23. DONS EN LIGNE

Le logiciel doit permettre aux personnes de déclarer ou d'effectuer des dons selon les moyens de paiement effectivement disponibles.

### 23.1 Informations à enregistrer

- Identité du donateur, si celui-ci souhaite la communiquer.
- Possibilité de don anonyme.
- Montant.
- Devise.
- Nature du don.
- Mode de paiement.
- Référence de transaction.
- Date de déclaration.
- Justificatif éventuel.
- Statut de vérification.

### 23.2 Statuts des dons

Le système doit pouvoir distinguer :

- Déclaré.
- En attente de vérification.
- Informations complémentaires demandées.
- Confirmé.
- Rejeté.
- Annulé.

Un don déclaré ne doit pas être comptabilisé automatiquement comme une recette confirmée. La confirmation doit dépendre d'une vérification effective ou d'une réponse fiable du prestataire de paiement.

### 23.3 Moyens de paiement

Les moyens proposés peuvent comprendre, selon le pays et les intégrations disponibles :

- Mobile Money.
- Virement bancaire.
- Autres moyens de paiement configurés.

Les reçus officiels doivent être générés après confirmation du paiement.

## 24. PORTAIL PERSONNEL DES MEMBRES

Chaque membre autorisé doit pouvoir accéder à un espace personnel sécurisé.

### 24.1 Fonctionnalités

- Consultation de son profil.
- Consultation de sa carte de membre.
- Accès à ses documents autorisés.
- Consultation de son historique de présence.
- Consultation de ses groupes et départements.
- Consultation des activités à venir.
- Réception des annonces.
- Soumission d'une demande de correction de profil.
- Consultation de son historique de contributions lorsqu'il est disponible et correctement associé.
- Gestion de sa session et de ses paramètres personnels.

### 24.2 Restrictions

Un membre ne doit pas pouvoir consulter :

- Les dossiers privés d'autres membres.
- Les notes pastorales confidentielles.
- Les données financières auxquelles il n'est pas autorisé à accéder.
- Les informations protégées concernant les enfants.
- Les documents internes réservés à l'administration.

Les demandes de modification de profil doivent suivre le processus de validation défini par l'Église.

## 25. GESTION DES ABONNEMENTS ET DE LA PLATEFORME

OmniChurch Connect doit intégrer un système central de gestion commerciale et technique.

### 25.1 Administration générale

L'administrateur principal de la plateforme doit pouvoir :

- Créer et gérer les comptes des Églises.
- Consulter leur état d'activation.
- Configurer les offres et abonnements.
- Définir les limites d'utilisation.
- Gérer les essais gratuits.
- Configurer les promotions et réductions.
- Suivre les paiements et renouvellements.
- Consulter l'historique des incidents.
- Administrer les paramètres globaux.
- Superviser la disponibilité du service.

### 25.2 Période d'essai et abonnements

Le système doit prévoir :

- Une période d'essai gratuite de sept jours à compter de son activation.
- Des abonnements mensuels et annuels.
- Des offres personnalisées.
- Des rappels avant expiration.
- L'historique des paiements.
- La gestion des échecs de paiement.
- La suspension en cas d'expiration selon les règles commerciales.
- La réactivation après confirmation du paiement.

La suspension d'un abonnement ne doit pas entraîner la suppression automatique des données de l'Église.

### 25.3 Contrôle des accès aux données

L'administrateur de la plateforme ne doit pas disposer d'un accès permanent et illimité aux informations confidentielles des Églises.

Tout accès exceptionnel justifié par une intervention technique ou de sécurité doit être limité dans le temps et dans son périmètre, et faire l'objet d'une journalisation.

## 26. SÉCURITÉ, SAUVEGARDE ET RESTAURATION

La sécurité doit être intégrée dès la conception de l'application.

### 26.1 Authentification

- Connexion sécurisée.
- Gestion des mots de passe.
- Récupération de compte.
- Protection contre les tentatives répétées de connexion.
- Gestion des sessions et appareils.
- Authentification à deux facteurs pour les comptes et opérations sensibles.
- Contrôle des autorisations côté serveur.

### 26.2 Isolation des Églises

Chaque Église doit posséder un espace de données strictement séparé.

Aucun utilisateur ne doit pouvoir consulter ou modifier les données d'une autre Église sans autorisation explicitement prévue par le système et dûment contrôlée.

### 26.3 Journal d'audit

Le système doit enregistrer les opérations sensibles, notamment :

- Les connexions et événements de sécurité.
- Les modifications des dossiers.
- Les opérations financières.
- Les validations et refus.
- Les changements de permissions.
- Les consultations de données confidentielles.
- Les opérations de suppression et d'archivage.
- Les interventions de l'administrateur de la plateforme.

Les utilisateurs ordinaires ne doivent pas pouvoir effacer ou modifier les traces d'audit.

### 26.4 Sauvegardes

Le système doit prévoir :

- Des sauvegardes chiffrées.
- Des sauvegardes régulières.
- Une politique de conservation.
- Des tests périodiques de restauration.
- Une procédure documentée de reprise après incident.
- Des droits stricts sur les sauvegardes.
- Une restauration contrôlée des données.

Les restaurations doivent respecter les suppressions légalement requises afin d'éviter la réapparition involontaire de données supprimées.

## 27. APPLICATION MULTILINGUE ET PERSONNALISATION

### 27.1 Langues

L'interface doit prendre en charge au minimum :

- Le français.
- L'anglais.

L'architecture doit permettre d'ajouter d'autres langues.

### 27.2 Préférences

Chaque Église doit pouvoir configurer :

- Sa langue par défaut.
- Son logo.
- Ses couleurs.
- Son fuseau horaire.
- Son format de date.
- Son format d'heure.

Chaque utilisateur doit pouvoir choisir sa langue et son thème personnel lorsque ces options sont disponibles.

Les contenus saisis par les utilisateurs ne doivent pas être traduits automatiquement sans action ou mécanisme clairement prévu.

## 28. INTERFACE ET EXPÉRIENCE UTILISATEUR

L'interface doit être moderne, professionnelle, institutionnelle et facile à utiliser.

### 28.1 Compatibilité

Le logiciel doit être utilisable sur :

- Ordinateurs.
- Tablettes.
- Smartphones Android.
- Navigateurs modernes.

Une application web progressive (PWA) est souhaitée pour permettre l'installation depuis un navigateur compatible.

### 28.2 Principes de conception

- Navigation claire.
- Menus adaptés aux permissions.
- Tableau de bord personnalisable.
- Recherche rapide.
- Formulaires accessibles.
- Tableaux lisibles.
- Interface responsive.
- Thème clair, sombre ou automatique.
- Identité visuelle personnalisable par Église.
- Messages d'erreur compréhensibles.
- Indication claire des opérations en attente.

## 29. FONCTIONNEMENT HORS LIGNE ET SYNCHRONISATION

Le logiciel doit permettre certaines opérations limitées lorsque la connexion Internet est indisponible.

### 29.1 Fonctionnalités concernées

Selon les possibilités techniques, le mode hors ligne peut prendre en charge :

- La consultation de données préalablement synchronisées et autorisées.
- La saisie de présences.
- La préparation de certaines opérations administratives.
- La mise en attente de modifications non sensibles.

### 29.2 Synchronisation

Le système doit :

- Afficher les données en attente de synchronisation.
- Indiquer les opérations synchronisées.
- Signaler les erreurs.
- Détecter les doublons potentiels.
- Identifier les conflits entre versions.
- Permettre une résolution contrôlée des conflits.

Les opérations financières critiques, les validations sensibles et les changements de permissions doivent nécessiter une connexion lorsque leur sécurité ne peut pas être garantie hors ligne.

## 30. ARCHITECTURE TECHNIQUE ET BASE DE DONNÉES

L'application doit reposer sur une architecture maintenable, sécurisée et évolutive.

### 30.1 Technologies de référence

Le générateur peut proposer une architecture adaptée reposant notamment sur :

- React et TypeScript pour l'interface.
- Une API sécurisée pour la logique métier.
- PostgreSQL ou une base relationnelle équivalente.
- Un système sécurisé de stockage des fichiers.
- Un mécanisme d'authentification et d'autorisation.
- Des services de sauvegarde et de surveillance.

Le choix définitif doit tenir compte des capacités du générateur, de l'hébergement et des exigences de sécurité.

### 30.2 Principales entités de données

La base de données doit notamment prévoir les entités suivantes :

- Églises.
- Utilisateurs.
- Rôles et permissions.
- Abonnements.
- Membres.
- Dossiers de validation.
- Groupes et départements.
- Présences.
- Activités et événements.
- Programmes.
- Intervenants.
- Documents.
- Certificats.
- Comptes et caisses.
- Recettes et dépenses.
- Budgets et projets.
- Dons.
- Biens et équipements.
- Dossiers pastoraux.
- Enfants et responsables légaux.
- Notifications.
- Publications.
- Journaux d'audit.
- Sauvegardes et historiques de synchronisation.

Les données propres à une Église doivent être liées à son identifiant de tenant et protégées par des contrôles d'accès côté serveur.

## 31. TESTS ET CRITÈRES D'ACCEPTATION

Avant la mise en production, le système doit faire l'objet de tests fonctionnels et techniques.

### 31.1 Tests fonctionnels

Vérifier notamment :

- La création d'une Église.
- La création et la gestion des comptes utilisateurs.
- L'attribution et la révocation des permissions.
- L'enregistrement et la validation des membres.
- La détection des doublons.
- La génération des documents officiels.
- L'enregistrement et la validation des opérations financières.
- Le suivi des activités.
- La production des rapports.
- Le fonctionnement du portail des membres.
- La gestion des abonnements.
- Les notifications et intégrations disponibles.

### 31.2 Tests de sécurité

- Vérifier l'isolation entre deux Églises.
- Vérifier les permissions sur chaque module.
- Tester les accès aux documents confidentiels.
- Tester la protection des opérations financières.
- Vérifier les journaux d'audit.
- Tester la récupération de compte.
- Vérifier la sauvegarde et la restauration.

### 31.3 Critères d'acceptation

Une fonctionnalité ne doit être considérée comme terminée que si :

- Elle fonctionne réellement.
- Ses données sont correctement enregistrées.
- Les permissions sont appliquées.
- Les erreurs sont gérées.
- Les opérations sensibles sont tracées.
- Les tests correspondants sont réussis.
- La documentation nécessaire est disponible.

Les boutons, écrans ou démonstrations visuelles ne doivent pas être considérés comme des fonctionnalités opérationnelles si aucune logique réelle n'est connectée.

## 32. DÉVELOPPEMENT PROGRESSIF

Le développement doit être réalisé par phases afin de garantir une base stable.

**Phase 1 : Fondations** — Architecture générale. Base de données. Isolation des Églises. Authentification. Gestion des utilisateurs. Rôles et permissions. Journal d'audit. Interface de base.

**Phase 2 : Première version opérationnelle** — Tableau de bord. Gestion des membres. Validation des inscriptions. Matricules. Recherche. Documents de base. Gestion des groupes. Présences.

**Phase 3 : Gestion quotidienne** — Calendrier. Activités et événements. Programmes. Intervenants. Communications. Bibliothèque documentaire.

**Phase 4 : Gestion financière** — Comptes et caisses. Recettes. Dépenses. Budgets. Projets. Rapprochements. Rapports financiers.

**Phase 5 : Modules spécialisés** — Suivi pastoral. Gestion des enfants. Patrimoine. Certificats avancés. Portail des membres. Gestion des demandes et rendez-vous.

**Phase 6 : Fonctions publiques et commerciales** — Site public des Églises. Dons en ligne. Abonnements. Gestion des offres. Notifications externes. Intégrations de paiement disponibles.

**Phase 7 : Fiabilité et déploiement** — Sécurité approfondie. Tests de charge. Sauvegardes. Restauration. Synchronisation hors ligne. Documentation. Formation. Déploiement en production.

## 33. LIVRABLES ATTENDUS

Le générateur d'applications par intelligence artificielle ou l'équipe de développement doit produire les éléments nécessaires à la création, au fonctionnement, à la maintenance et à l'évolution d'OmniChurch Connect.

### 33.1 Livrables techniques

- Le code source complet de l'application.
- Le schéma de la base de données.
- Les scripts de création et de migration de la base de données.
- Le système d'authentification.
- Le système de gestion des rôles et des permissions.
- Les API nécessaires au fonctionnement des modules.
- Les interfaces utilisateur responsives.
- Les modèles de documents administratifs et financiers.
- Les mécanismes de sauvegarde et de restauration.
- Les règles de sécurité et d'isolation des données entre les Églises.
- Les tests automatisés pertinents.
- Les journaux d'audit des opérations sensibles.

### 33.2 Documentation

Le projet doit également comprendre :

- La documentation technique.
- Le guide d'installation et de configuration.
- Le guide d'administration de la plateforme.
- Le guide d'utilisation destiné aux Églises.
- La procédure de sauvegarde et de restauration.
- La procédure de déploiement et de mise à jour.
- La documentation de la base de données.
- La documentation des intégrations externes.

### 33.3 État réel du développement

Le générateur doit fournir une liste claire distinguant :

- Les fonctionnalités terminées et testées.
- Les fonctionnalités développées mais non encore validées.
- Les fonctionnalités partiellement implémentées.
- Les fonctionnalités en attente de configuration.
- Les fonctionnalités non développées.
- Les intégrations nécessitant un compte externe, une clé API ou un abonnement.

Aucune fonctionnalité ne doit être déclarée opérationnelle si elle n'a pas été réellement implémentée et vérifiée.

## 34. INSTRUCTIONS FINALES AU GÉNÉRATEUR D'APPLICATIONS IA

Construis OmniChurch Connect comme une véritable plateforme professionnelle de gestion ecclésiastique multi-Églises, sécurisée, modulaire, évolutive et accessible sur ordinateur, tablette et smartphone.

L'objectif est de fournir un logiciel opérationnel permettant à plusieurs Églises de gérer leurs membres, leurs finances, leurs activités, leurs départements, leurs documents, leur patrimoine, leur suivi pastoral et leurs communications dans un environnement numérique centralisé.

### 34.1 Principes fondamentaux de développement

1. Application réellement fonctionnelle : ne produis pas uniquement une maquette graphique ou des pages statiques.
2. Données persistantes : toutes les données doivent être enregistrées dans une base de données adaptée et rester disponibles après déconnexion, redémarrage ou changement d'appareil.
3. Architecture multi-Églises : chaque Église doit disposer de son propre espace et ses données doivent être isolées de celles des autres Églises.
4. Sécurité des accès : les rôles et permissions doivent être appliqués côté serveur, et pas uniquement dans l'interface.
5. Traçabilité : les opérations administratives, financières et confidentielles doivent être journalisées selon leur niveau de sensibilité.
6. Interface professionnelle : adopte une identité visuelle élégante, institutionnelle, moderne et cohérente.
7. Bilinguisme : prévois le français et l'anglais, avec possibilité d'ajouter d'autres langues.
8. Compatibilité mobile : adapte toutes les interfaces aux smartphones, tablettes et ordinateurs.
9. Évolutivité : développe les modules de manière indépendante, tout en assurant leur intégration.
10. Fiabilité : prévois des mécanismes de validation, de gestion des erreurs, de sauvegarde et de restauration.

### 34.2 Ordre obligatoire de réalisation

Commence par la fondation technique avant de développer l'ensemble des modules.

**Phase 1 — Fondations techniques** : architecture générale, base de données, authentification, gestion des utilisateurs, gestion des rôles et permissions, isolation des données des Églises, journal d'audit, structure générale de l'interface.

**Phase 2 — Première version opérationnelle** : tableau de bord, gestion des membres, validation des inscriptions, attribution des matricules, recherche et détection des doublons, gestion des groupes, gestion des présences, documents administratifs de base.

**Phase 3 — Gestion quotidienne** : calendrier, activités et événements, programmes, intervenants, communications, gestion documentaire.

**Phase 4 — Gestion financière** : comptes et caisses, recettes et dépenses, budgets et projets, contributions, rapprochements, rapports financiers.

**Phase 5 — Modules spécialisés** : suivi pastoral, gestion des enfants, patrimoine, certificats avancés, portail des membres, demandes et rendez-vous.

**Phase 6 — Fonctions publiques et commerciales** : sites publics des Églises, dons en ligne, abonnements, gestion des offres et paiements, notifications externes, intégrations disponibles.

**Phase 7 — Sécurité et mise en production** : tests approfondis, tests de charge, sauvegardes, restauration, synchronisation hors ligne, documentation, déploiement en production.

### 34.3 Vérifications obligatoires à chaque phase

Avant de passer à la phase suivante, le générateur doit :

- Vérifier le fonctionnement réel des fonctionnalités développées.
- Vérifier que les données sont correctement enregistrées.
- Tester les autorisations des différents profils utilisateurs.
- Vérifier l'isolation des données entre plusieurs Églises.
- Tester les scénarios d'erreur.
- Vérifier les règles de validation.
- Contrôler la traçabilité des opérations sensibles.
- Corriger les anomalies identifiées.
- Documenter les fonctionnalités achevées et celles qui restent à développer.

### 34.4 Règles de gestion des intégrations

Les services externes, notamment les paiements, les SMS, WhatsApp, les courriers électroniques et les autres plateformes, ne doivent être présentés comme opérationnels que si les intégrations nécessaires ont été configurées et testées.

Si une intégration n'est pas disponible, le logiciel doit afficher clairement son état et proposer une procédure de configuration, sans simuler une opération réussie.

### 34.5 Exigences relatives à la livraison finale

À la fin du développement, fournir une application utilisable, une base de données fonctionnelle, le code source, les instructions de déploiement, les procédures de sauvegarde et la documentation nécessaire à l'administration.

Le logiciel doit pouvoir être déployé sur une infrastructure adaptée et conserver ses données dans le temps.

**Instruction prioritaire** : commence immédiatement par la Phase 1, sans reprendre une longue série de questions déjà traitées. Si une information technique indispensable manque, choisis une solution standard compatible avec l'architecture retenue, documente ce choix et poursuis le développement.

Le résultat attendu est une plateforme professionnelle, bilingue, sécurisée et évolutive, capable de répondre aux besoins administratifs, financiers, pastoraux et organisationnels de plusieurs Églises au sein d'OmniChurch Connect.

---

*Document de référence OmniChurch Connect — 34 sections. Version consolidée le 28 octobre 2026.*
*Inspire by YuuStore · +243 977 555 768*
