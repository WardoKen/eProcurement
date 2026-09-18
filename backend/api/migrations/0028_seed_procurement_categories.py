from django.db import migrations

# The full PhilGEPS-style procurement category vocabulary. Historically only
# referenced as a dead `OPPORTUNITY_CATEGORIES` list in api/views.py - never
# actually loaded into the `Category` table, so PR Category Selection and
# Supplier Registration (both of which read from `Category`) only ever showed
# whatever handful of categories an admin had manually created. Seeding it
# here makes the full vocabulary available everywhere `Category` is used.
PROCUREMENT_CATEGORIES = [
    'Advertising Agency Services', 'Agricultural Chemicals',
    'Agricultural Machinery and Equipment',
    'Agricultural Products (Seeds, Seedlings, Plants..)',
    'Airconditioning and Airconditioning Systems',
    'Airconditioning Maintenance Services', 'Aircraft Spare Parts',
    'Ammunitions and Explosives', 'Animal Feeds', 'Appliances',
    'Architectural Design', 'Arts and Crafts Accessories and Supplies',
    'Audio and Visual Equipment', 'Automation Equipment', 'Aviation Products',
    'Aviation Services', 'Bedclothes, Linens and Towels', 'Beverages',
    'Books, Maps and Other Publications', 'Cargo Forwarding and Hauling Services',
    'Catering Services', 'Chemical Detergents', 'Chemicals and Chemical Products',
    'Communication Equipment',
    'Communication Equipment & Parts and Accessories', 'Computer Furniture',
    'Construction Equipment', 'Construction Management Services',
    'Construction Materials and Supplies', 'Construction Projects',
    'Consulting Services', 'Corporate Giveaways', 'Dairy Products',
    'Diagnostic and Laboratory Services', 'Drugs and Medicines',
    'Editorial, Design, Graphic and Fine Art Services',
    'Educational Materials and Supplies', 'Electrical Supplies',
    'Electrical Systems and Lighting Components',
    'Electronic Parts and Components',
    'Engineering and Laboratory Testing Equipment',
    'Environmental Health/Safety Equipment', 'Events Management', 'Fertilizers',
    'Fire Fighting & Rescue and Safety Equipment', 'Fixtures', 'Flags',
    'Food Processing Equipment', 'Food Stuff', 'Freight Forwarder Services',
    'Fuels/Fuel Additives & Lubricants & Anti Corrosive', 'Furniture',
    'Furniture Parts and Accessories', 'Games and Toys',
    'Gaming Equipment and Paraphernalia', 'Garments', 'General Contractor',
    'General Engineering Services', 'General Merchandise',
    'General Repair and Maintenance Services', 'Geotechnical Instrumentation',
    'Grocery Items', 'Guns and Weapons', 'Hardware and Construction Supplies',
    'Helicopters - Parts', 'Horizontal Directional Drilling',
    'Hospital / Medical Equipment', 'Hospital / Medical Equipment Services',
    'Hotel and Lodging and Meeting Facilities', 'Hydrological Instruments',
    'Industrial Machinery and Equipment', 'Industrial pumps and compressors',
    'Industrial Safety Equipment', 'Information Technology',
    'Information Technology Parts & Peripheral',
    'Institutional food services equipment', 'Internet Services',
    'Investigative Equipment', 'IT Broadcasting and Telecommunications',
    'Janitorial Equipment', 'Janitorial Services', 'Janitorial Supplies',
    'Kitchenware', 'Laboratory Supplies and Equipment', 'Laundry Services',
    'Lease and Rental of Property or Building',
    'Lifting equipment and accessories',
    'Live Animals (Livestock, Birds, Live fish & etc..)', 'Machine Tools',
    'Mail and Cargo Transport Services', 'Mailing Supplies', 'Marine Transport',
    'Maritime Spare Parts', 'Market Research Services',
    'Medical and Dental Equipment', 'Medical Supplies and Laboratory Instrument',
    'Metal Fabrication', 'Meteorological Equipments and Instruments',
    'Microfilm Equipment', 'Microfilm Equipment - Supplies and Accesories',
    'Mining Equipment and Supplies', 'Musical Instrument Parts and Accesories',
    'Musical Instruments', 'Navigation Equipment', 'Newspapers',
    'Office Equipment', 'Office Equipment Parts and Accessories',
    'Office Equipment Supplies and Consumables', 'Office Supplies and Devices',
    'Oil/Heat Chemical Resistant Rubber', 'Ordnance Products',
    'Packaging Supplies and Materials', 'Personal Care Products',
    'Pest Control Products', 'Pest Control Services', 'Photographic Equipment',
    'Photographic Parts, Supplies and Accessories', 'Photography Services',
    'Plastic Products', 'Power Generation and Distribution Machinery',
    'Preserved or Processed Foods', 'Print and Broadcast and Aerial Advertising',
    'Printing Services', 'Printing Supplies',
    'Public Relations Programs or Services', 'Purses, handbags and bags',
    'Pyrotechnics and Fireworks', 'Quartermaster Items',
    'Radiological/Diagnostic Equipment',
    'Real Estate Developement and Maintenance', 'Reproduction Services',
    'Rice Milling Services', 'Safety and Occupational Products',
    'Sale of Property or Building', 'Security Services',
    'Security Surveillance and Detection Equipment', 'Services',
    'Signage and Accessories', 'Sporting Goods', 'Structured Cabling',
    'Sub-station Contractors', 'Surveying Instruments', 'Surveying Services',
    'Systems Integration', 'Telecommunications Engineering',
    'Telecommunications Provider', 'Textiles',
    'Timepieces and Jewelry and Gemstone Products', 'Tokens and Awards',
    'Traffic Control Systems', 'Transmission and Distribution Lines',
    'Transportation and Communications Services',
    'Travel, Food, Lodging and Entertainment Services',
    'Vehicle Parts and Accessories', 'Vehicle Repair and Maintenance',
    'Vehicles', 'Veterinary Products and Supplies', 'Video Production Services',
    'Waste Management and Recycling',
    'Water and Waste Water Treatment Supply & Disposal',
    'Water Service Connection Materials/Fittings',
    'Well Drilling and Construction Services',
]


def seed_categories(apps, schema_editor):
    category_model = apps.get_model('api', 'Category')
    for name in PROCUREMENT_CATEGORIES:
        category_model.objects.get_or_create(name=name, defaults={'is_active': True})


def noop(apps, schema_editor):
    # Left in place on rollback - by the time this seed data is in use,
    # suppliers/PR items/RFQs may already reference these categories via a
    # PROTECT foreign key, so an unconditional delete here could fail.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0027_add_pr_notification_settings'),
    ]

    operations = [
        migrations.RunPython(seed_categories, noop),
    ]
