{
 "cells": [
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "import os, json, csv\n",
    "from label_utils import stage_to_group, map_malignant_type\n",
    "\n",
    "base = \"/tf/dataset/dataset001/049.난소암 데이터/3.개방데이터/1.데이터/\"\n",
    "meta_path = os.path.join(base, \"Other/메타데이터/암/EMR\")\n",
    "\n",
    "pt_stage = {}\n",
    "pt_type = {}\n",
    "for f in os.listdir(meta_path):\n",
    "    pt = f.split(\".\")[0]\n",
    "    with open (os.path.join(meta_path, f), \"r\", encoding='utf-8') as fp:\n",
    "        m=json.load(fp)\n",
    "    pt_stage[pt] = stage_to_group(m.get(\"FIGO_STAG\"))\n",
    "    pt_type[pt] = map_malignant_type(m.get(\"FND\"))\n",
    "    \n",
    "print(\"meta loaded:\", len(pt_stage))"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.6.9"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 2
}
