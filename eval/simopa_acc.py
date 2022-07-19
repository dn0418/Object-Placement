import argparse
import datetime
import os
import torch
from tqdm import tqdm
import numpy as np
import torch

from simopa_cfg import opt
from simopa_dst import ImageDataset
from simopa_net import ObjectPlaceNet


def evaluate(args):
    # modify configs
    opt.dataset_path = os.path.join('result', args.expid, args.eval_type, str(args.epoch))
    assert (os.path.exists(opt.dataset_path))
    opt.img_path = opt.dataset_path
    opt.mask_path = opt.dataset_path
    opt.test_data_path = os.path.join(opt.dataset_path, '{}.csv'.format(args.eval_type))
    opt.test_box_dic_path = os.path.join(opt.dataset_path, '{}_bboxes.npy'.format(args.eval_type))
    opt.test_reference_feature_path = os.path.join(opt.dataset_path, '{}_feats.npy'.format(args.eval_type))
    opt.test_target_feature_path = os.path.join(opt.dataset_path, '{}_fgfeats.npy'.format(args.eval_type))

    opt.relation_method = 5
    opt.attention_method = 2
    opt.refer_num = 5
    opt.attention_head = 16
    opt.without_mask = False
    opt.without_global_feature = False

    net = ObjectPlaceNet(backbone_pretrained=False)

    checkpoint_path = args.checkpoint
    print('load pretrained weights from ', checkpoint_path)
    net.load_state_dict(torch.load(checkpoint_path))
    net = net.cuda().eval()

    total = 0
    pred_labels = []
    sample_ids = []

    testset = ImageDataset(istrain=False)
    test_loader = torch.utils.data.DataLoader(testset, batch_size=128,
                                              shuffle=False, num_workers=2,
                                              drop_last=False, pin_memory=True)

    with torch.no_grad():
        for batch_index, (sample_id, img_cat, label, target_box, refer_box, target_feats, refer_feats, target_mask, refer_mask, tar_class, w, h) in enumerate(
                tqdm(test_loader)):
            img_cat, label, target_box, refer_box, target_mask, refer_mask, w, h = img_cat.cuda(), label.cuda(), target_box.cuda(
                ), refer_box.cuda(), target_mask.cuda(), refer_mask.cuda(), w.cuda(), h.cuda()
            target_feats, refer_feats = target_feats.cuda(), refer_feats.cuda()
            logits, weights = net(img_cat, target_box, refer_box, target_feats, refer_feats, target_mask, refer_mask, w, h)
            pred_labels.extend(logits.max(1)[1].cpu().numpy())
            total += label.size(0)
            sample_ids.extend(list(sample_id))

    pred_acc = (np.array(pred_labels, dtype=np.int32) == 1).sum() / len(pred_labels)
    pred_dic = {}
    for _id, _label in zip(sample_ids, pred_labels):
        if _id in pred_dic:
            pred_dic[_id].append(_label)
        else:
            pred_dic[_id] = [_label]
    pred_acc_list = []
    for _, _label_list in pred_dic.items():
        id_acc = (np.array(_label_list, dtype=np.int32) == 1).sum() / len(_label_list)
        pred_acc_list.append(id_acc)
    pred_acc_no_replica = sum(pred_acc_list) / len(pred_acc_list)
    print(" - Evaluate on {} pairs of (fg, bg) images, pred_acc={:.4f}".format(total, pred_acc))
    print(" - Evaluate on {} (no_replica) pairs of (fg, bg) images, pred_acc={:.4f}".format(len(pred_acc_list), pred_acc_no_replica))
    mark = 'a' if os.path.exists(os.path.join(opt.dataset_path, "{}_acc.txt".format(args.eval_type))) else 'w'
    with open(os.path.join(opt.dataset_path, "{}_acc.txt".format(args.eval_type)), mark) as f:
        f.write("{}\n".format(datetime.datetime.now()))
        f.write(" - Evaluate on {} pairs of (fg, bg) images, pred_acc={:.4f}\n".format(total, pred_acc))
        f.write(" - Evaluate on {} (no_replica) pairs of (fg, bg) images, pred_acc={:.4f}\n".format(len(pred_acc_list), pred_acc_no_replica))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=str, required=True, help="path to loaded checkpoint")
    parser.add_argument("--expid", type=str, required=True, help="experiment name")
    parser.add_argument("--epoch", type=int, required=True, help="epoch for evaluation")
    parser.add_argument("--eval_type", type=str, default="eval", help="evaluation type")
    args = parser.parse_args()
    assert os.path.exists(args.checkpoint)
    evaluate(args)
