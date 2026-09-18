"""Tests for the promises this app makes to its two audiences.

There is one enxoval, served at the site root, and anybody may open it. The
owner signs in somewhere else. Most of what is worth testing lives on that
boundary: a visitor must leave a name and a working e-mail before they can
reserve anything, must never see who reserved what, and must not be able to
reach another account's items.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APITestCase

from .models import Claim, Item, Registry

User = get_user_model()

PUBLIC = "/api/public/"
REGISTRY = "/api/registry/"


def make_owner(username="owner", email="owner@example.com"):
    return User.objects.create_user(username=username, password="pw-for-tests", email=email)


def make_registry(owner, **kwargs):
    kwargs.setdefault("title", "Enxoval Missionário")
    return Registry.objects.create(owner=owner, **kwargs)


def make_item(registry, **kwargs):
    kwargs.setdefault("name", "Jogo de panelas")
    return Item.objects.create(registry=registry, **kwargs)


def make_claim(item, **kwargs):
    kwargs.setdefault("first_name", "Ana")
    kwargs.setdefault("last_name", "Ribeiro")
    kwargs.setdefault("email", "ana@example.com")
    return Claim.objects.create(item=item, **kwargs)


class SingleRegistryTests(TestCase):
    """There is one enxoval. load() is how everything finds it."""

    def test_the_owners_enxoval_is_created_on_first_use(self):
        owner = make_owner()
        self.assertEqual(Registry.objects.count(), 0)
        registry = Registry.load(owner=owner)
        self.assertEqual(registry.owner, owner)
        self.assertEqual(Registry.objects.count(), 1)

    def test_loading_again_returns_the_same_one_rather_than_a_second(self):
        owner = make_owner()
        first = Registry.load(owner=owner)
        self.assertEqual(Registry.load(owner=owner).pk, first.pk)
        self.assertEqual(Registry.objects.count(), 1)

    def test_an_existing_enxoval_is_never_replaced(self):
        owner = make_owner()
        existing = make_registry(owner, title="O de sempre")
        self.assertEqual(Registry.load(owner=owner).pk, existing.pk)
        self.assertEqual(Registry.load(owner=owner).title, "O de sempre")

    def test_the_public_side_finds_it_without_an_account(self):
        registry = make_registry(make_owner())
        self.assertEqual(Registry.load().pk, registry.pk)

    def test_the_public_side_skips_an_unpublished_enxoval(self):
        make_registry(make_owner(), is_published=False)
        self.assertIsNone(Registry.load())

    def test_the_public_side_is_empty_when_nothing_exists_yet(self):
        self.assertIsNone(Registry.load())

    def test_a_second_accounts_enxoval_never_takes_over_the_public_page(self):
        """Tirar o enxoval do ar derruba a página, em vez de promover outro."""
        first = make_registry(make_owner("a", "a@example.com"))
        make_registry(make_owner("b", "b@example.com"), title="De outra pessoa")
        self.assertEqual(Registry.load().pk, first.pk)
        first.is_published = False
        first.save()
        self.assertIsNone(Registry.load())

    def test_each_account_keeps_its_own(self):
        a, b = make_owner("a", "a@example.com"), make_owner("b", "b@example.com")
        self.assertNotEqual(Registry.load(owner=a).pk, Registry.load(owner=b).pk)


class HealthCheckTests(TestCase):
    """O deploy só segue em frente se isto responder 200."""

    def test_a_healthy_app_reports_ok(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "database": True})

    def test_no_login_required(self):
        self.assertNotIn("WWW-Authenticate", self.client.get("/healthz").headers)

    def test_a_database_that_is_down_reports_503(self):
        """Um processo web que responde sem banco não está saudável."""
        with patch("registry.views.connections") as connections:
            connections.__getitem__.return_value.cursor.side_effect = OSError("sem conexão")
            with self.assertLogs("registry.views", level="ERROR"):
                response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"ok": False, "database": False})

    def test_the_spa_catch_all_does_not_swallow_it(self):
        """A rota do React pega quase tudo; /healthz precisa escapar dela."""
        self.assertEqual(self.client.get("/healthz")["Content-Type"], "application/json")


class ClaimNameTests(TestCase):
    def test_the_display_name_joins_the_two_halves(self):
        claim = make_claim(make_item(make_registry(make_owner())))
        self.assertEqual(claim.name, "Ana Ribeiro")


class QuantityTests(TestCase):
    def setUp(self):
        self.item = make_item(make_registry(make_owner()), quantity_needed=3)

    def claim(self, quantity, status=Claim.Status.PENDING):
        return make_claim(self.item, quantity=quantity, status=status)

    def test_counts_start_empty(self):
        self.assertEqual(self.item.quantity_claimed, 0)
        self.assertEqual(self.item.quantity_remaining, 3)
        self.assertFalse(self.item.is_fully_claimed)

    def test_claims_add_up_across_people(self):
        self.claim(1)
        self.claim(2)
        self.assertEqual(self.item.quantity_remaining, 0)
        self.assertTrue(self.item.is_fully_claimed)

    def test_cancelled_claims_free_the_item_back_up(self):
        self.claim(3, status=Claim.Status.CANCELLED)
        self.assertEqual(self.item.quantity_remaining, 3)
        self.assertFalse(self.item.is_fully_claimed)

    def test_contacted_and_received_claims_still_hold_their_quantity(self):
        self.claim(1, status=Claim.Status.CONTACTED)
        self.claim(1, status=Claim.Status.FULFILLED)
        self.assertEqual(self.item.quantity_remaining, 1)

    def test_remaining_never_goes_negative(self):
        self.claim(9)
        self.assertEqual(self.item.quantity_remaining, 0)

    def test_deleting_an_item_deletes_its_claims(self):
        self.claim(1)
        self.item.delete()
        self.assertEqual(Claim.objects.count(), 0)


class PublicPageTests(APITestCase):
    def setUp(self):
        cache.clear()  # reservas são limitadas por IP, e os testes dividem um só
        self.owner = make_owner()
        self.registry = make_registry(
            self.owner,
            intro="Obrigado por nos ajudar!",
            contact_note="Entraremos em contato esta semana.",
        )
        self.item = make_item(self.registry, quantity_needed=2)

    def test_the_root_page_returns_the_enxoval(self):
        response = self.client.get(PUBLIC)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["title"], self.registry.title)
        self.assertEqual(response.data["intro"], "Obrigado por nos ajudar!")
        self.assertEqual(len(response.data["items"]), 1)

    def test_items_carry_the_counts_the_page_renders(self):
        item = self.client.get(PUBLIC).data["items"][0]
        self.assertEqual(item["quantity_needed"], 2)
        self.assertEqual(item["quantity_remaining"], 2)
        self.assertFalse(item["is_fully_claimed"])

    def test_no_login_required(self):
        self.assertNotIn("WWW-Authenticate", self.client.get(PUBLIC).headers)

    def test_an_unpublished_enxoval_is_a_404(self):
        self.registry.is_published = False
        self.registry.save()
        self.assertEqual(self.client.get(PUBLIC).status_code, 404)

    def test_visitors_never_see_who_reserved_what(self):
        make_claim(self.item, first_name="Ana", last_name="Ribeiro", message="Parabéns!")
        body = self.client.get(PUBLIC).content.decode()
        for private in ("Ana", "Ribeiro", "ana@example.com", "Parabéns"):
            self.assertNotIn(private, body)
        self.assertIn('"quantity_remaining":1', body.replace(" ", ""))

    def test_the_owner_notification_address_is_not_public(self):
        self.registry.notify_email = "secreto@example.com"
        self.registry.save()
        self.assertNotIn("secreto@example.com", self.client.get(PUBLIC).content.decode())


class ReserveTests(APITestCase):
    """Nome, sobrenome e e-mail no topo da página são obrigatórios."""

    def setUp(self):
        cache.clear()
        self.owner = make_owner()
        self.registry = make_registry(
            self.owner, contact_note="Entraremos em contato esta semana."
        )
        self.item = make_item(self.registry, quantity_needed=2)

    def url(self, item=None):
        return f"{PUBLIC}items/{(item or self.item).id}/claim/"

    def post(self, **overrides):
        body = {"first_name": "Ana", "last_name": "Ribeiro", "email": "ana@example.com"}
        body.update(overrides)
        return self.client.post(self.url(), body, format="json")

    def test_a_visitor_with_all_three_fields_can_reserve(self):
        response = self.post()
        self.assertEqual(response.status_code, 201)
        claim = Claim.objects.get()
        self.assertEqual(claim.name, "Ana Ribeiro")
        self.assertEqual(claim.email, "ana@example.com")
        self.assertEqual(claim.status, Claim.Status.PENDING)

    def test_the_response_tells_the_visitor_what_happens_next(self):
        response = self.post()
        self.assertEqual(response.data["contact_note"], "Entraremos em contato esta semana.")
        self.assertEqual(response.data["item"]["quantity_remaining"], 1)

    def test_a_missing_first_name_blocks_the_reservation(self):
        for value in ({}, {"first_name": ""}, {"first_name": "   "}):
            body = {"last_name": "Ribeiro", "email": "ana@example.com", **value}
            response = self.client.post(self.url(), body, format="json")
            self.assertEqual(response.status_code, 400, value)
            self.assertIn("first_name", response.data)
        self.assertEqual(Claim.objects.count(), 0)

    def test_a_missing_last_name_blocks_the_reservation(self):
        for value in ({}, {"last_name": ""}, {"last_name": "   "}):
            body = {"first_name": "Ana", "email": "ana@example.com", **value}
            response = self.client.post(self.url(), body, format="json")
            self.assertEqual(response.status_code, 400, value)
            self.assertIn("last_name", response.data)
        self.assertEqual(Claim.objects.count(), 0)

    def test_a_missing_email_blocks_the_reservation(self):
        for value in ({}, {"email": ""}):
            body = {"first_name": "Ana", "last_name": "Ribeiro", **value}
            response = self.client.post(self.url(), body, format="json")
            self.assertEqual(response.status_code, 400, value)
            self.assertIn("email", response.data)
        self.assertEqual(Claim.objects.count(), 0)

    def test_a_malformed_email_blocks_the_reservation(self):
        response = self.post(email="ana-arroba-example")
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)
        self.assertEqual(Claim.objects.count(), 0)

    def test_the_error_messages_are_in_portuguese(self):
        response = self.client.post(self.url(), {}, format="json")
        joined = " ".join(str(v) for v in response.data.values())
        self.assertIn("Preencha seu nome", joined)
        self.assertIn("Preencha seu sobrenome", joined)
        self.assertIn("Preencha seu e-mail", joined)

    def test_a_phone_number_is_no_longer_accepted_in_place_of_an_email(self):
        """O formulário público agora pede e-mail; telefone não substitui."""
        response = self.client.post(
            self.url(),
            {"first_name": "Ana", "last_name": "Ribeiro", "phone": "+55 11 90000-0000"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Claim.objects.count(), 0)

    def test_several_people_can_reserve_one_multi_quantity_item(self):
        self.assertEqual(self.post(first_name="Ana").status_code, 201)
        self.assertEqual(self.post(first_name="Bruno").status_code, 201)
        self.assertEqual(Claim.objects.count(), 2)
        self.assertTrue(Item.objects.get(pk=self.item.pk).is_fully_claimed)

    def test_reserving_more_than_is_left_is_rejected(self):
        response = self.post(quantity=3)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Faltam apenas 2", str(response.data["quantity"]))

    def test_a_fully_reserved_item_cannot_be_reserved_again(self):
        self.post(quantity=2)
        self.assertEqual(self.post(first_name="Bruno").status_code, 400)
        self.assertEqual(Claim.objects.count(), 1)

    def test_zero_quantity_is_rejected(self):
        self.assertEqual(self.post(quantity=0).status_code, 400)

    def test_a_cancelled_reservation_reopens_the_item(self):
        self.post(quantity=2)
        Claim.objects.update(status=Claim.Status.CANCELLED)
        self.assertEqual(self.post(first_name="Bruno").status_code, 201)

    def test_an_item_from_another_account_cannot_be_reserved(self):
        """O id do item vem na URL, então a busca tem de ficar presa ao enxoval público."""
        other = make_item(make_registry(make_owner("outro", "outro@example.com")))
        self.assertEqual(self.post_to(other).status_code, 404)
        self.assertEqual(Claim.objects.count(), 0)

    def post_to(self, item):
        return self.client.post(
            self.url(item),
            {"first_name": "Ana", "last_name": "Ribeiro", "email": "ana@example.com"},
            format="json",
        )

    def test_an_unpublished_enxoval_accepts_no_reservations(self):
        self.registry.is_published = False
        self.registry.save()
        self.assertEqual(self.post().status_code, 404)
        self.assertEqual(Claim.objects.count(), 0)

    def test_reservations_are_rate_limited_per_ip(self):
        item = make_item(self.registry, name="Toalhas", quantity_needed=100)
        url = self.url(item)
        body = {"first_name": "Ana", "last_name": "Ribeiro", "email": "ana@example.com"}
        for _ in range(20):
            self.assertEqual(self.client.post(url, body, format="json").status_code, 201)
        self.assertEqual(self.client.post(url, body, format="json").status_code, 429)

    def test_a_forged_forwarded_for_header_buys_no_extra_reservations(self):
        """Behind a proxy the rate limit has to key on the IP the proxy saw.

        NUM_PROXIES makes DRF read X-Forwarded-For from the right, where the
        closest proxy writes. Without it DRF keys on the whole header, and any
        visitor can mint a fresh allowance by inventing a new left-hand value.
        """
        item = make_item(self.registry, name="Toalhas", quantity_needed=200)
        url = self.url(item)
        body = {"first_name": "Ana", "last_name": "Ribeiro", "email": "ana@example.com"}

        # Rightmost address is what Caddy appends: the same visitor throughout.
        for i in range(20):
            response = self.client.post(
                url, body, format="json", HTTP_X_FORWARDED_FOR=f"10.0.0.{i}, 203.0.113.9"
            )
            self.assertEqual(response.status_code, 201, f"request {i}")

        blocked = self.client.post(
            url, body, format="json", HTTP_X_FORWARDED_FOR="10.9.9.9, 203.0.113.9"
        )
        self.assertEqual(blocked.status_code, 429)

    def test_a_different_visitor_still_gets_their_own_allowance(self):
        """The fix must not lump every visitor behind the proxy into one bucket."""
        item = make_item(self.registry, name="Toalhas", quantity_needed=200)
        url = self.url(item)
        body = {"first_name": "Ana", "last_name": "Ribeiro", "email": "ana@example.com"}

        for _ in range(20):
            self.client.post(url, body, format="json", HTTP_X_FORWARDED_FOR="203.0.113.9")
        self.assertEqual(
            self.client.post(
                url, body, format="json", HTTP_X_FORWARDED_FOR="203.0.113.9"
            ).status_code,
            429,
        )
        # Someone else, arriving through the same proxy, is unaffected.
        self.assertEqual(
            self.client.post(
                url, body, format="json", HTTP_X_FORWARDED_FOR="198.51.100.7"
            ).status_code,
            201,
        )


class NotificationTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.owner = make_owner()
        self.registry = make_registry(self.owner)
        self.item = make_item(self.registry)

    def reserve(self, **overrides):
        body = {
            "first_name": "Ana",
            "last_name": "Ribeiro",
            "email": "ana@example.com",
            "message": "Feliz em ajudar",
        }
        body.update(overrides)
        return self.client.post(f"{PUBLIC}items/{self.item.id}/claim/", body, format="json")

    def test_the_owner_is_emailed(self):
        self.reserve()
        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ["owner@example.com"])
        self.assertIn("Ana Ribeiro", sent.subject)
        self.assertIn("Jogo de panelas", sent.subject)

    def test_the_email_is_in_portuguese_and_carries_everything_needed_to_reply(self):
        self.reserve()
        body = mail.outbox[0].body
        for expected in ("Ana Ribeiro", "ana@example.com", "Feliz em ajudar", "Entre em contato"):
            self.assertIn(expected, body)

    def test_notify_email_overrides_the_account_address(self):
        self.registry.notify_email = "esposa@example.com"
        self.registry.save()
        self.reserve()
        self.assertEqual(mail.outbox[0].to, ["esposa@example.com"])

    def test_an_owner_with_no_address_anywhere_is_simply_not_emailed(self):
        self.owner.email = ""
        self.owner.save()
        with self.assertLogs("registry.views", level="WARNING"):
            self.assertEqual(self.reserve().status_code, 201)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(Claim.objects.count(), 1)

    def test_an_smtp_outage_never_loses_the_reservation(self):
        with patch("registry.views.send_mail", side_effect=OSError("SMTP fora do ar")):
            with self.assertLogs("registry.views", level="ERROR"):
                response = self.reserve()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Claim.objects.count(), 1)


class OwnerApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.owner = make_owner()
        self.registry = make_registry(self.owner)
        self.item = make_item(self.registry, quantity_needed=2)
        self.claim = make_claim(self.item, quantity=1)

        self.stranger = make_owner("stranger", "stranger@example.com")
        self.stranger_registry = make_registry(self.stranger, title="De outra pessoa")
        self.stranger_item = make_item(self.stranger_registry)
        self.stranger_claim = make_claim(self.stranger_item, first_name="Bruno")

    def sign_in(self, user=None):
        self.client.force_authenticate(user or self.owner)

    # --- authentication ---------------------------------------------------

    def test_login_returns_a_token_pair(self):
        response = self.client.post(
            "/api/auth/login/", {"username": "owner", "password": "pw-for-tests"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_a_wrong_password_does_not(self):
        response = self.client.post(
            "/api/auth/login/", {"username": "owner", "password": "nope"}, format="json"
        )
        self.assertEqual(response.status_code, 401)

    def test_an_access_token_actually_opens_the_owner_api(self):
        token = self.client.post(
            "/api/auth/login/", {"username": "owner", "password": "pw-for-tests"}, format="json"
        ).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(self.client.get(REGISTRY).status_code, 200)

    def test_the_owner_api_is_closed_to_visitors(self):
        for path in (REGISTRY, "/api/items/", "/api/claims/"):
            self.assertEqual(self.client.get(path).status_code, 401, path)

    # --- the one enxoval --------------------------------------------------

    def test_the_owner_gets_their_enxoval_with_no_id_in_the_url(self):
        self.sign_in()
        data = self.client.get(REGISTRY).data
        self.assertEqual(data["id"], self.registry.id)
        self.assertEqual(data["title"], self.registry.title)
        self.assertEqual(data["pending_claims"], 1)

    def test_a_brand_new_account_gets_one_created_rather_than_a_404(self):
        fresh = make_owner("fresh", "fresh@example.com")
        self.sign_in(fresh)
        response = self.client.get(REGISTRY)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Registry.objects.filter(owner=fresh).count(), 1)

    def test_each_account_sees_only_its_own_enxoval(self):
        self.sign_in(self.stranger)
        self.assertEqual(self.client.get(REGISTRY).data["id"], self.stranger_registry.id)

    def test_pending_count_ignores_claims_already_dealt_with(self):
        Claim.objects.filter(pk=self.claim.pk).update(status=Claim.Status.FULFILLED)
        self.sign_in()
        self.assertEqual(self.client.get(REGISTRY).data["pending_claims"], 0)

    def test_the_owner_edits_the_title_and_notes(self):
        self.sign_in()
        response = self.client.patch(
            REGISTRY, {"title": "Enxoval da Ana", "intro": "Oi!"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.registry.refresh_from_db()
        self.assertEqual(self.registry.title, "Enxoval da Ana")
        self.assertEqual(self.registry.intro, "Oi!")

    def test_unpublishing_takes_the_public_page_down(self):
        self.sign_in()
        self.client.patch(REGISTRY, {"is_published": False}, format="json")
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(PUBLIC).status_code, 404)

    def test_there_is_no_way_to_create_or_delete_a_second_enxoval(self):
        self.sign_in()
        self.assertEqual(self.client.post(REGISTRY, {"title": "Outro"}, format="json").status_code, 405)
        self.assertEqual(self.client.delete(REGISTRY).status_code, 405)
        self.assertEqual(Registry.objects.filter(owner=self.owner).count(), 1)

    # --- items ------------------------------------------------------------

    def test_the_item_list_never_leaks_across_accounts(self):
        self.sign_in()
        ids = [i["id"] for i in self.client.get("/api/items/").data]
        self.assertEqual(ids, [self.item.id])

    def test_an_item_shows_the_owner_who_reserved_it(self):
        self.sign_in()
        item = self.client.get(f"/api/items/{self.item.id}/").data
        self.assertEqual(item["quantity_claimed"], 1)
        self.assertEqual(item["quantity_remaining"], 1)
        self.assertEqual([c["name"] for c in item["claims"]], ["Ana Ribeiro"])

    def test_adding_an_item(self):
        self.sign_in()
        response = self.client.post(
            "/api/items/",
            {"registry": self.registry.id, "name": "Filtro de água", "quantity_needed": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.registry.items.count(), 2)

    def test_you_cannot_add_an_item_to_another_accounts_enxoval(self):
        self.sign_in()
        response = self.client.post(
            "/api/items/", {"registry": self.stranger_registry.id, "name": "Nada"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.stranger_registry.items.count(), 1)

    def test_you_cannot_move_your_item_onto_another_accounts_enxoval(self):
        self.sign_in()
        response = self.client.patch(
            f"/api/items/{self.item.id}/", {"registry": self.stranger_registry.id}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.item.refresh_from_db()
        self.assertEqual(self.item.registry, self.registry)

    def test_another_accounts_item_cannot_be_edited_or_deleted(self):
        self.sign_in()
        path = f"/api/items/{self.stranger_item.id}/"
        self.assertEqual(self.client.patch(path, {"name": "Meu"}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(path).status_code, 404)
        self.assertTrue(Item.objects.filter(pk=self.stranger_item.pk).exists())

    def test_deleting_an_item_deletes_the_reservations_on_it(self):
        self.sign_in()
        self.assertEqual(self.client.delete(f"/api/items/{self.item.id}/").status_code, 204)
        self.assertFalse(Claim.objects.filter(pk=self.claim.pk).exists())

    # --- reservations -----------------------------------------------------

    def test_the_owner_sees_who_is_buying_what(self):
        self.sign_in()
        response = self.client.get("/api/claims/")
        self.assertEqual(len(response.data), 1)
        row = response.data[0]
        self.assertEqual(row["name"], "Ana Ribeiro")
        self.assertEqual(row["first_name"], "Ana")
        self.assertEqual(row["last_name"], "Ribeiro")
        self.assertEqual(row["email"], "ana@example.com")
        self.assertEqual(row["item_name"], "Jogo de panelas")

    def test_the_reservation_list_never_leaks_across_accounts(self):
        self.sign_in()
        names = [c["name"] for c in self.client.get("/api/claims/").data]
        self.assertEqual(names, ["Ana Ribeiro"])

    def test_pending_returns_only_reservations_still_awaiting_a_reply(self):
        self.sign_in()
        make_claim(self.item, first_name="Bruno", status=Claim.Status.CONTACTED)
        names = [c["name"] for c in self.client.get("/api/claims/pending/").data]
        self.assertEqual(names, ["Ana Ribeiro"])

    def test_the_owner_moves_a_reservation_along(self):
        self.sign_in()
        for status_value in (Claim.Status.CONTACTED, Claim.Status.FULFILLED):
            response = self.client.patch(
                f"/api/claims/{self.claim.id}/", {"status": status_value}, format="json"
            )
            self.assertEqual(response.status_code, 200)
            self.claim.refresh_from_db()
            self.assertEqual(self.claim.status, status_value)

    def test_cancelling_a_reservation_frees_the_item_up_again(self):
        self.sign_in()
        self.client.patch(
            f"/api/claims/{self.claim.id}/", {"status": Claim.Status.CANCELLED}, format="json"
        )
        self.assertEqual(Item.objects.get(pk=self.item.pk).quantity_remaining, 2)

    def test_what_the_giver_wrote_is_not_rewritable(self):
        """O dono acompanha o contato; não reescreve o que a pessoa escreveu."""
        self.sign_in()
        self.client.patch(
            f"/api/claims/{self.claim.id}/",
            {
                "first_name": "Editado",
                "last_name": "Editado",
                "email": "editado@example.com",
                "quantity": 2,
            },
            format="json",
        )
        self.claim.refresh_from_db()
        self.assertEqual(self.claim.name, "Ana Ribeiro")
        self.assertEqual(self.claim.email, "ana@example.com")
        self.assertEqual(self.claim.quantity, 1)

    def test_reservations_cannot_be_invented_from_the_owner_side(self):
        self.sign_in()
        response = self.client.post(
            "/api/claims/", {"item": self.item.id, "first_name": "Fantasma"}, format="json"
        )
        self.assertEqual(response.status_code, 405)

    def test_another_accounts_reservation_is_untouchable(self):
        self.sign_in()
        path = f"/api/claims/{self.stranger_claim.id}/"
        self.assertEqual(
            self.client.patch(path, {"status": Claim.Status.CANCELLED}, format="json").status_code,
            404,
        )
        self.assertEqual(self.client.delete(path).status_code, 404)
        self.stranger_claim.refresh_from_db()
        self.assertEqual(self.stranger_claim.status, Claim.Status.PENDING)
