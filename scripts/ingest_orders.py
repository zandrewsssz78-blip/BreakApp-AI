"""Incorpora pedidos nuevos validados y conserva copia previa antes de modificar datos."""
import argparse, csv, json, shutil, sys
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"/"raw"
sys.path.insert(0,str(ROOT/"src"))
from break_ia.data_loader import load_products, ORDER_CSV_FIELDS

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input",required=True,help="CSV con el mismo esquema de order_history.csv")
    ap.add_argument("--retrain",action="store_true",help="Entrenar el agente tras incorporar los pedidos")
    args=ap.parse_args()
    incoming=list(csv.DictReader(open(args.input,encoding="utf-8-sig",newline="")))
    if not incoming:
        raise SystemExit("El archivo no contiene pedidos.")
    if set(ORDER_CSV_FIELDS)-set(incoming[0]):
        raise SystemExit("El CSV no contiene todas las columnas requeridas.")
    catalog=load_products(DATA/"products_catalog.csv")
    current_path=DATA/"order_history.csv"
    current=list(csv.DictReader(open(current_path,encoding="utf-8",newline="")))
    known_orders={r["order_id"] for r in current}
    known_keys={(r["order_id"],r["product_id"]) for r in current}
    by_order={}
    for row in incoming:
        pid=row["product_id"]
        if pid not in catalog:
            raise SystemExit(f"Producto inexistente: {pid}")
        product=catalog[pid]
        if row["product_name"] != product.name or row["category"] != product.category.value:
            raise SystemExit(f"Los datos del producto {pid} no coinciden con el catálogo.")
        if row["restaurant_id"] != product.restaurant_id:
            raise SystemExit(f"Restaurante incorrecto para {pid}.")
        if int(row["unit_price"]) != product.price:
            raise SystemExit(f"Precio distinto al catálogo para {pid}.")
        qty=int(row["quantity"])
        if qty <= 0 or int(row["total_price"]) != qty*product.price:
            raise SystemExit(f"Cantidad o total inválido en {row['order_id']}.")
        datetime.strptime(row["timestamp"],"%Y-%m-%d %H:%M:%S")
        key=(row["order_id"],pid)
        if key in known_keys:
            raise SystemExit(f"Posible pedido duplicado: {key}.")
        known_keys.add(key)
        by_order.setdefault(row["order_id"],set()).add(row["user_id"])
    if set(by_order)&known_orders:
        raise SystemExit("Uno o más order_id ya existen; no se modificó la base.")
    if any(len(users)!=1 for users in by_order.values()):
        raise SystemExit("Un order_id está asociado a más de un usuario.")
    backup=ROOT/"data"/"backups"
    backup.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(current_path,backup/f"order_history_{stamp}.csv")
    current.extend(incoming)
    current.sort(key=lambda r:(r["timestamp"],r["order_id"],r["product_id"]))
    with open(current_path,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=ORDER_CSV_FIELDS);w.writeheader();w.writerows(current)
    master=DATA/"breakapp_synthetic_dataset.json"
    if master.exists():
        obj=json.loads(master.read_text(encoding="utf-8"))
        obj["order_history"]=current
        obj.setdefault("metadata",{})["total_order_lines"]=len(current)
        obj["metadata"]["total_orders"]=len({r["order_id"] for r in current})
        obj["metadata"]["last_ingestion"]=stamp
        master.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Pedidos incorporados: {len(by_order)} | Líneas nuevas: {len(incoming)}")
    print(f"Respaldo: data/backups/order_history_{stamp}.csv")
    if args.retrain:
        import subprocess
        subprocess.run([sys.executable,str(ROOT/"scripts"/"train_agent.py")],check=True)
if __name__=="__main__":
    main()
