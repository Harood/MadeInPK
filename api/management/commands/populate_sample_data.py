from decimal import Decimal
import random
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from api.models import (
    Address,
    AuctionListing,
    Bid,
    Category,
    City,
    FixedPriceListing,
    Product,
    ProductImage,
    SellerProfile,
    Order,
    OrderItem,
    Feedback,
    Payment,
)


User = get_user_model()


class Command(BaseCommand):
    help = "Populate sample users, products, fixed listings, auction listings, and bids"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete existing products/listings/auctions/bids before seeding",
        )
        parser.add_argument(
            "--images-dir",
            default=str(Path(settings.MEDIA_ROOT) / "sample_images"),
            help="Directory containing manually provided product images",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Seeding sample marketplace data...")

        if not Category.objects.exists():
            self.stdout.write(self.style.WARNING("Categories missing, running populate_categories..."))
            from django.core.management import call_command

            call_command("populate_categories")

        if not City.objects.exists():
            self.stdout.write(self.style.WARNING("Locations missing, running populate_locations..."))
            from django.core.management import call_command

            call_command("populate_locations")

        if options["force"]:
            self.stdout.write(self.style.WARNING("Clearing existing demo listings and products..."))
            from api.models import Order, OrderItem, Payment
            Order.objects.all().delete()
            OrderItem.objects.all().delete()
            Payment.objects.all().delete()
            Bid.objects.all().delete()
            AuctionListing.objects.all().delete()
            FixedPriceListing.objects.all().delete()
            Product.objects.all().delete()

        self.images_dir = Path(options["images_dir"])
        self._create_demo_users_and_profiles()
        self._create_demo_products_and_listings()
        self._create_demo_orders_and_feedback()

        self.stdout.write(self.style.SUCCESS("Sample marketplace data seeded successfully."))
        self.stdout.write(
            self.style.SUCCESS(
                f"Summary: {User.objects.count()} users, {Product.objects.count()} products, "
                f"{FixedPriceListing.objects.count()} fixed listings, {AuctionListing.objects.count()} auctions, "
                f"{Order.objects.count()} orders"
            )
        )

    def _create_demo_users_and_profiles(self):
        sellers = [
            {
                "email": "seller1@madeinpk.local",
                "username": "seller_one",
                "first_name": "Ali",
                "last_name": "Khan",
                "brand_name": "Khan Crafts",
                "biography": "Handmade artisan goods from Lahore.",
            },
            {
                "email": "seller2@madeinpk.local",
                "username": "seller_two",
                "first_name": "Ayesha",
                "last_name": "Riaz",
                "brand_name": "Riaz Textiles",
                "biography": "Traditional textile products from Faisalabad.",
            },
            {
                "email": "seller3@madeinpk.local",
                "username": "seller_three",
                "first_name": "Hamza",
                "last_name": "Iqbal",
                "brand_name": "Iqbal Pottery",
                "biography": "Clay and ceramic art pieces.",
            },
        ]

        buyers = [
            {
                "email": "buyer1@madeinpk.local",
                "username": "buyer_one",
                "first_name": "Sara",
                "last_name": "Noor",
            },
            {
                "email": "buyer2@madeinpk.local",
                "username": "buyer_two",
                "first_name": "Usman",
                "last_name": "Zafar",
            },
            {
                "email": "buyer3@madeinpk.local",
                "username": "buyer_three",
                "first_name": "Mariam",
                "last_name": "Javed",
            },
        ]

        cities = list(City.objects.select_related("province")[:6])
        if not cities:
            raise ValueError("No cities available to assign addresses.")

        self.seller_users = []
        self.buyer_users = []

        for i, seller_data in enumerate(sellers):
            user, created = User.objects.get_or_create(
                email=seller_data["email"],
                defaults={
                    "username": seller_data["username"],
                    "first_name": seller_data["first_name"],
                    "last_name": seller_data["last_name"],
                    "role": "seller",
                },
            )
            if created:
                user.set_password("seller123")
                user.save()

            if user.role != "seller":
                user.role = "seller"
                user.save(update_fields=["role"])

            city = cities[i % len(cities)]
            address, _ = Address.objects.get_or_create(
                user=user,
                street_address=f"House {10 + i}, Demo Street",
                city=city,
                postal_code=f"54{100 + i}",
                defaults={"is_default": True},
            )

            if not user.addresses.filter(is_default=True).exists():
                address.is_default = True
                address.save(update_fields=["is_default"])

            SellerProfile.objects.get_or_create(
                user=user,
                defaults={
                    "brand_name": seller_data["brand_name"],
                    "biography": seller_data["biography"],
                    "business_phone": "0300-0000000",
                    "business_address_id": address,
                    "is_verified": True,
                },
            )

            self.seller_users.append(user)

        for i, buyer_data in enumerate(buyers):
            user, created = User.objects.get_or_create(
                email=buyer_data["email"],
                defaults={
                    "username": buyer_data["username"],
                    "first_name": buyer_data["first_name"],
                    "last_name": buyer_data["last_name"],
                    "role": "buyer",
                },
            )
            if created:
                user.set_password("buyer123")
                user.save()

            city = cities[(i + 3) % len(cities)]
            Address.objects.get_or_create(
                user=user,
                street_address=f"Flat {20 + i}, Buyer Avenue",
                city=city,
                postal_code=f"75{100 + i}",
                defaults={"is_default": True},
            )

            self.buyer_users.append(user)

    def _create_demo_products_and_listings(self):
        categories = list(Category.objects.all())
        if not categories:
            raise ValueError("No categories found to assign products.")

        conditions = ["new", "like_new", "good", "fair"]
        now = timezone.now()

        fixed_templates = [
            ("Multani Blue Pottery Plate", "Decorative blue pottery plate with traditional Multani patterns."),
            ("Ralli Quilt", "Hand-stitched ralli quilt with vibrant geometric patchwork."),
            ("Kashmiri Embroidered Shawl", "Elegant Kashmiri shawl with fine embroidery and soft finish."),
            ("Truck Art Water Jug", "Colorful water jug decorated with Pakistani truck art motifs."),
            ("Balochi Mirror Work Bag", "Handmade bag featuring mirror work and Balochi embroidery."),
            ("Chitrali Wool Cap", "Warm wool cap inspired by traditional Chitrali winter wear."),
            ("Brass Surahi", "Classic brass surahi with a polished traditional look."),
            ("Handwoven Sindhi Ralli Pillow Cover", "Handwoven pillow cover with Sindhi ralli textile patterns."),
            ("Wooden Charpai Miniature", "Miniature wooden charpai crafted as a cultural decor piece."),
            ("Ceramic Tea Set", "Ceramic tea set with hand-painted regional detailing."),
        ]

        auction_templates = [
            ("Vintage Pottery Set", "Rare hand-painted pottery set ideal for collectors."),
            ("Brass Tea Set", "Classic brass tea set with engraved floral design."),
            ("Kashmiri Carpet", "Detailed handwoven carpet with premium wool."),
            ("Onyx Table Lamp", "Handcrafted onyx stone lamp with polished finish."),
            ("Calligraphy Canvas", "Urdu calligraphy canvas by local artist."),
            ("Antique Wooden Mirror", "Solid wood mirror frame with antique style carving."),
        ]

        fixed_created = 0
        auction_created = 0

        for idx, (name, description) in enumerate(fixed_templates):
            seller = self.seller_users[idx % len(self.seller_users)]
            category = categories[idx % len(categories)]
            product, created = Product.objects.get_or_create(
                seller=seller,
                name=name,
                defaults={
                    "category": category,
                    "description": description,
                    "condition": conditions[idx % len(conditions)],
                },
            )

            self._attach_product_images(product, idx, "fixed")

            if created:
                FixedPriceListing.objects.create(
                    product=product,
                    price=Decimal(str(1500 + (idx * 750))),
                    quantity=5 + (idx % 4),
                    status="active",
                    featured=(idx % 2 == 0),
                )
                fixed_created += 1

        for idx, (name, description) in enumerate(auction_templates):
            seller = self.seller_users[idx % len(self.seller_users)]
            category = categories[(idx + 2) % len(categories)]
            product, created = Product.objects.get_or_create(
                seller=seller,
                name=name,
                defaults={
                    "category": category,
                    "description": description,
                    "condition": conditions[(idx + 1) % len(conditions)],
                },
            )

            self._attach_product_images(product, idx, "auction")

            if not created and hasattr(product, "auction"):
                continue

            starting_price = Decimal(str(3000 + (idx * 1000)))
            auction = AuctionListing.objects.create(
                product=product,
                starting_price=starting_price,
                current_price=starting_price,
                start_time=now - timezone.timedelta(hours=2),
                end_time=now + timezone.timedelta(days=2, hours=idx),
                status="active",
            )

            bidders = random.sample(self.buyer_users, k=min(2, len(self.buyer_users)))
            current = starting_price
            for bid_index, bidder in enumerate(bidders):
                bid_amount = current + Decimal(str(250 + (bid_index * 150)))
                Bid.objects.create(
                    auction=auction,
                    bidder=bidder,
                    amount=bid_amount,
                    is_winning=False,
                )
                current = bid_amount

            latest_bid = auction.bids.order_by("-amount", "-bid_time").first()
            if latest_bid:
                latest_bid.is_winning = True
                latest_bid.save(update_fields=["is_winning"])
                auction.current_price = latest_bid.amount
                auction.save(update_fields=["current_price"])

            auction_created += 1

        self.stdout.write(
            f"Created {fixed_created} fixed listings and {auction_created} auction listings."
        )

    def _attach_product_images(self, product, seed_index, listing_kind):
        if ProductImage.objects.filter(product=product).exists():
            return

        if not self.images_dir.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"No manual images directory found at {self.images_dir}. "
                    "Create it and add PNG/JPG files to seed product images."
                )
            )
            return

        product_slug = slugify(product.name)
        listing_slug = slugify(listing_kind)
        candidate_prefixes = [
            f"{product_slug}_{listing_slug}",
            f"{product_slug}",
        ]

        matching_files = []
        for prefix in candidate_prefixes:
            matching_files = sorted(
                [
                    path for path in self.images_dir.iterdir()
                    if path.is_file()
                    and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
                    and path.stem.lower().startswith(prefix)
                ]
            )
            if matching_files:
                break

        if not matching_files:
            self.stdout.write(
                self.style.WARNING(
                    f"No matching images found for '{product.name}' in {self.images_dir}."
                )
            )
            return

        for image_index, image_path in enumerate(matching_files[:3]):
            with image_path.open("rb") as image_file:
                product_image = ProductImage.objects.create(
                    product=product,
                    is_primary=(image_index == 0),
                    order=image_index,
                )
                product_image.image.save(image_path.name, image_file, save=True)

    def _create_demo_orders_and_feedback(self):
        now = timezone.now()
        
        # Create sample orders for fixed-price listings
        fixed_listings = FixedPriceListing.objects.all()
        
        for listing in fixed_listings[:6]:  # Create orders for first 6 fixed listings
            # Pick a random buyer and create an order
            buyer = random.choice(self.buyer_users)
            seller = listing.product.seller
            buyer_address = buyer.addresses.first()
            
            if not buyer_address:
                # Create a default address if buyer has none
                cities = list(City.objects.all())
                if cities:
                    city = cities[0]
                    buyer_address = Address.objects.create(
                        user=buyer,
                        street_address=f"Address for {buyer.username}",
                        city=city,
                        postal_code="75000",
                        is_default=True,
                    )
            
            if buyer_address:
                # Generate a unique order number
                order_code = f"FIX-{random.randint(100000000, 999999999):09d}"
                
                # Calculate prices
                total_amount = listing.price * Decimal("2")  # 2 quantity
                platform_fee = total_amount * Decimal("0.02")
                seller_amount = total_amount - platform_fee
                
                order = Order.objects.create(
                    order_number=order_code,
                    buyer=buyer,
                    seller=seller,
                    product=listing.product,
                    order_type="fixed_price",
                    quantity=2,
                    unit_price=listing.price,
                    total_amount=total_amount,
                    platform_fee=platform_fee,
                    seller_amount=seller_amount,
                    shipping_address=buyer_address,
                    status="paid",
                    paid_at=now - timezone.timedelta(days=random.randint(1, 10)),
                )
                
                # Create OrderItem
                OrderItem.objects.create(
                    order=order,
                    product=listing.product,
                    quantity=2,
                    unit_price=listing.price,
                )
                
                # Create Feedback with ratings
                rating = random.randint(3, 5)  # 3-5 stars
                Feedback.objects.create(
                    order=order,
                    buyer=buyer,
                    seller=seller,
                    seller_rating=rating,
                    seller_comment="Great product and fast shipping!",
                    platform_rating=rating,
                    platform_comment="Excellent platform experience",
                    communication_rating=rating,
                    shipping_speed_rating=rating,
                    product_as_described=True,
                )
        
        # Create sample orders for auction listings
        auction_listings = AuctionListing.objects.filter(status="active")
        
        for auction in auction_listings[:3]:  # Create orders for first 3 auctions
            # Get the latest winning bid
            latest_bid = auction.bids.order_by("-amount").first()
            
            if latest_bid:
                buyer = latest_bid.bidder
                seller = auction.product.seller
                buyer_address = buyer.addresses.first()
                
                if not buyer_address:
                    cities = list(City.objects.all())
                    if cities:
                        city = cities[0]
                        buyer_address = Address.objects.create(
                            user=buyer,
                            street_address=f"Address for {buyer.username}",
                            city=city,
                            postal_code="75000",
                            is_default=True,
                        )
                
                if buyer_address:
                    # Generate a unique order number for auction
                    order_code = f"AUC-{random.randint(100000000, 999999999):09d}"
                    
                    # Calculate prices
                    total_amount = latest_bid.amount
                    platform_fee = total_amount * Decimal("0.02")
                    seller_amount = total_amount - platform_fee
                    
                    order = Order.objects.create(
                        order_number=order_code,
                        buyer=buyer,
                        seller=seller,
                        product=auction.product,
                        auction=auction,
                        order_type="auction",
                        quantity=1,
                        unit_price=latest_bid.amount,
                        total_amount=total_amount,
                        platform_fee=platform_fee,
                        seller_amount=seller_amount,
                        shipping_address=buyer_address,
                        status="paid",
                        paid_at=now - timezone.timedelta(days=random.randint(1, 5)),
                    )
                    
                    # Create OrderItem
                    OrderItem.objects.create(
                        order=order,
                        product=auction.product,
                        quantity=1,
                        unit_price=latest_bid.amount,
                    )
                    
                    # Create Feedback
                    rating = random.randint(3, 5)  # 3-5 stars
                    Feedback.objects.create(
                        order=order,
                        buyer=buyer,
                        seller=seller,
                        seller_rating=rating,
                        seller_comment="Won the auction! Very happy with the purchase.",
                        platform_rating=rating,
                        platform_comment="Smooth auction process",
                        communication_rating=rating,
                        shipping_speed_rating=rating,
                        product_as_described=True,
                    )
        
        self.stdout.write(self.style.SUCCESS(f"Created sample orders and feedback ratings."))