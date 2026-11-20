default_hooks = dict(
    checkpoint=dict(interval=1, type='CheckpointHook'),
    logger=dict(interval=50, type='LoggerHook'),
    param_scheduler=dict(type='ParamSchedulerHook'),
    sampler_seed=dict(type='DistSamplerSeedHook'),
    timer=dict(type='IterTimerHook'),
    visualization=dict(draw=False, type='TrackVisualizationHook'))
default_scope = 'mmdet'
detector = dict(
    as_two_stage=True,
    backbone=dict(
        attn_drop_rate=0.0,
        convert_weights=False,
        depths=[
            2,
            2,
            18,
            2,
        ],
        drop_path_rate=0.3,
        drop_rate=0.0,
        embed_dims=128,
        mlp_ratio=4,
        num_heads=[
            4,
            8,
            16,
            32,
        ],
        out_indices=(
            1,
            2,
            3,
        ),
        patch_norm=True,
        pretrain_img_size=384,
        qk_scale=None,
        qkv_bias=True,
        type='SwinTransformer',
        window_size=12,
        with_cp=False),
    bbox_head=dict(
        contrastive_cfg=dict(max_text_len=256),
        loss_bbox=dict(loss_weight=5.0, type='L1Loss'),
        loss_cls=dict(
            alpha=0.25,
            gamma=2.0,
            loss_weight=1.0,
            type='FocalLoss',
            use_sigmoid=True),
        num_classes=80,
        sync_cls_avg_factor=True,
        type='GroundingDINOHead'),
    decoder=dict(
        layer_cfg=dict(
            cross_attn_cfg=dict(dropout=0.0, embed_dims=256, num_heads=8),
            cross_attn_text_cfg=dict(dropout=0.0, embed_dims=256, num_heads=8),
            ffn_cfg=dict(
                embed_dims=256, feedforward_channels=2048, ffn_drop=0.0),
            self_attn_cfg=dict(dropout=0.0, embed_dims=256, num_heads=8)),
        num_layers=6,
        post_norm_cfg=None,
        return_intermediate=True),
    dn_cfg=dict(
        box_noise_scale=1.0,
        group_cfg=dict(dynamic=True, num_dn_queries=100, num_groups=None),
        label_noise_scale=0.5),
    encoder=dict(
        fusion_layer_cfg=dict(
            embed_dim=1024,
            init_values=0.0001,
            l_dim=256,
            num_heads=4,
            v_dim=256),
        layer_cfg=dict(
            ffn_cfg=dict(
                embed_dims=256, feedforward_channels=2048, ffn_drop=0.0),
            self_attn_cfg=dict(dropout=0.0, embed_dims=256, num_levels=4)),
        num_layers=6,
        text_layer_cfg=dict(
            ffn_cfg=dict(
                embed_dims=256, feedforward_channels=1024, ffn_drop=0.0),
            self_attn_cfg=dict(dropout=0.0, embed_dims=256, num_heads=4))),
    init_cfg=dict(
        checkpoint=
        'saved_models/pretrain_weights/groundingdino_swinb_cogcoor_mmdet-55949c9c.pth',
        type='Pretrained'),
    language_model=dict(
        add_pooling_layer=True,
        name='bert-base-uncased',
        pad_to_max=False,
        special_tokens_list=[
            '[CLS]',
            '[SEP]',
            '.',
            '?',
        ],
        type='BertModel',
        use_sub_sentence_represent=True),
    neck=dict(
        act_cfg=None,
        bias=True,
        in_channels=[
            256,
            512,
            1024,
        ],
        kernel_size=1,
        norm_cfg=dict(num_groups=32, type='GN'),
        num_outs=4,
        out_channels=256,
        type='ChannelMapper'),
    num_queries=900,
    positional_encoding=dict(
        normalize=True, num_feats=128, offset=0.0, temperature=20),
    test_cfg=dict(max_per_img=300),
    train_cfg=None,
    type='GroundingDINOMasa',
    with_box_refine=True)
env_cfg = dict(
    cudnn_benchmark=False,
    dist_cfg=dict(backend='nccl'),
    mp_cfg=dict(mp_start_method='fork', opencv_num_threads=0))
inference_pipeline = [
    dict(
        transforms=[
            dict(keep_ratio=True, scale=(
                1333,
                800,
            ), type='Resize'),
        ],
        type='TransformBroadcaster'),
    dict(type='PackTrackInputs'),
]
key = 'lang_model_name'
keys_to_delete = [
    'dataset_type',
    'data_root',
    'backend_args',
    'train_pipeline',
    'test_pipeline',
    'train_dataloader',
    'val_dataloader',
    'test_dataloader',
    'val_evaluator',
    'test_evaluator',
    'train_cfg',
    'val_cfg',
    'test_cfg',
    'param_scheduler',
    'optim_wrapper',
    'auto_scale_lr',
    'default_scope',
    'default_hooks',
    'env_cfg',
    'vis_backends',
    'visualizer',
    'log_processor',
    'log_level',
    'load_from',
    'resume',
    'lang_model_name',
]
load_from = None
log_level = 'INFO'
log_processor = dict(by_epoch=True, type='LogProcessor', window_size=50)
model = dict(
    data_preprocessor=dict(
        bgr_to_rgb=True,
        mean=[
            123.675,
            116.28,
            103.53,
        ],
        pad_mask=False,
        pad_size_divisor=32,
        std=[
            58.395,
            57.12,
            57.375,
        ],
        type='TrackDataPreprocessor'),
    detector=dict(
        as_two_stage=True,
        backbone=dict(
            attn_drop_rate=0.0,
            convert_weights=False,
            depths=[
                2,
                2,
                18,
                2,
            ],
            drop_path_rate=0.3,
            drop_rate=0.0,
            embed_dims=128,
            mlp_ratio=4,
            num_heads=[
                4,
                8,
                16,
                32,
            ],
            out_indices=(
                1,
                2,
                3,
            ),
            patch_norm=True,
            pretrain_img_size=384,
            qk_scale=None,
            qkv_bias=True,
            type='SwinTransformer',
            window_size=12,
            with_cp=False),
        bbox_head=dict(
            contrastive_cfg=dict(max_text_len=256),
            loss_bbox=dict(loss_weight=5.0, type='L1Loss'),
            loss_cls=dict(
                alpha=0.25,
                gamma=2.0,
                loss_weight=1.0,
                type='FocalLoss',
                use_sigmoid=True),
            num_classes=80,
            sync_cls_avg_factor=True,
            type='GroundingDINOHead'),
        decoder=dict(
            layer_cfg=dict(
                cross_attn_cfg=dict(dropout=0.0, embed_dims=256, num_heads=8),
                cross_attn_text_cfg=dict(
                    dropout=0.0, embed_dims=256, num_heads=8),
                ffn_cfg=dict(
                    embed_dims=256, feedforward_channels=2048, ffn_drop=0.0),
                self_attn_cfg=dict(dropout=0.0, embed_dims=256, num_heads=8)),
            num_layers=6,
            post_norm_cfg=None,
            return_intermediate=True),
        dn_cfg=dict(
            box_noise_scale=1.0,
            group_cfg=dict(dynamic=True, num_dn_queries=100, num_groups=None),
            label_noise_scale=0.5),
        encoder=dict(
            fusion_layer_cfg=dict(
                embed_dim=1024,
                init_values=0.0001,
                l_dim=256,
                num_heads=4,
                v_dim=256),
            layer_cfg=dict(
                ffn_cfg=dict(
                    embed_dims=256, feedforward_channels=2048, ffn_drop=0.0),
                self_attn_cfg=dict(dropout=0.0, embed_dims=256, num_levels=4)),
            num_layers=6,
            text_layer_cfg=dict(
                ffn_cfg=dict(
                    embed_dims=256, feedforward_channels=1024, ffn_drop=0.0),
                self_attn_cfg=dict(dropout=0.0, embed_dims=256, num_heads=4))),
        init_cfg=dict(
            checkpoint=
            'saved_models/pretrain_weights/groundingdino_swinb_cogcoor_mmdet-55949c9c.pth',
            type='Pretrained'),
        language_model=dict(
            add_pooling_layer=True,
            name='/data2/user/toc_phase0/models/MASA/bert-base-uncased',
            pad_to_max=False,
            special_tokens_list=[
                '[CLS]',
                '[SEP]',
                '.',
                '?',
            ],
            type='BertModel',
            use_sub_sentence_represent=True),
        neck=dict(
            act_cfg=None,
            bias=True,
            in_channels=[
                256,
                512,
                1024,
            ],
            kernel_size=1,
            norm_cfg=dict(num_groups=32, type='GN'),
            num_outs=4,
            out_channels=256,
            type='ChannelMapper'),
        num_queries=900,
        positional_encoding=dict(
            normalize=True, num_feats=128, offset=0.0, temperature=20),
        test_cfg=dict(max_per_img=300),
        train_cfg=None,
        type='GroundingDINOMasa',
        with_box_refine=True),
    freeze_detector=True,
    load_public_dets=False,
    masa_adapter=[
        dict(
            in_channels=[
                256,
                512,
                1024,
            ],
            norm_cfg=dict(requires_grad=True, type='SyncBN'),
            num_outs=5,
            out_channels=256,
            type='FPN'),
        dict(
            in_channels=256,
            num_blocks=3,
            out_channels=256,
            type='DeformFusion'),
    ],
    roi_head=dict(
        bbox_head=dict(
            bbox_coder=dict(
                target_means=[
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                ],
                target_stds=[
                    0.1,
                    0.1,
                    0.2,
                    0.2,
                ],
                type='DeltaXYWHBBoxCoder'),
            fc_out_channels=1024,
            in_channels=256,
            loss_bbox=dict(loss_weight=1.0, type='L1Loss'),
            loss_cls=dict(
                loss_weight=1.0, type='CrossEntropyLoss', use_sigmoid=False),
            num_classes=1,
            reg_class_agnostic=True,
            roi_feat_size=7,
            type='Shared2FCBBoxHead'),
        bbox_roi_extractor=dict(
            featmap_strides=[
                8,
                16,
                32,
            ],
            out_channels=256,
            roi_layer=dict(output_size=7, sampling_ratio=0, type='RoIAlign'),
            type='SingleRoIExtractor'),
        type='StandardRoIHead'),
    rpn_head=dict(
        anchor_generator=dict(
            ratios=[
                0.5,
                1.0,
                2.0,
            ],
            scales=[
                8,
            ],
            strides=[
                8,
                16,
                32,
                64,
                128,
            ],
            type='AnchorGenerator'),
        bbox_coder=dict(
            target_means=[
                0.0,
                0.0,
                0.0,
                0.0,
            ],
            target_stds=[
                1.0,
                1.0,
                1.0,
                1.0,
            ],
            type='DeltaXYWHBBoxCoder'),
        feat_channels=256,
        in_channels=256,
        loss_bbox=dict(
            beta=0.1111111111111111, loss_weight=1.0, type='SmoothL1Loss'),
        loss_cls=dict(
            loss_weight=1.0, type='CrossEntropyLoss', use_sigmoid=True),
        type='RPNHead'),
    test_cfg=dict(
        rcnn=dict(
            mask_thr_binary=0.5,
            max_per_img=50,
            nms=dict(
                class_agnostic=True,
                iou_threshold=0.5,
                split_thr=100000,
                type='nms'),
            score_thr=0.02),
        rpn=dict(
            max_per_img=1000,
            min_bbox_size=0,
            nms=dict(iou_threshold=0.7, type='nms'),
            nms_pre=1000)),
    track_head=dict(
        embed_head=dict(
            embed_channels=256,
            loss_track=dict(loss_weight=0.25, type='UnbiasedContrastLoss'),
            loss_track_aux=dict(
                hard_mining=True,
                loss_weight=1.0,
                neg_margin=0.1,
                neg_pos_ub=3,
                pos_margin=0,
                type='MarginL2Loss'),
            norm_cfg=dict(num_groups=32, type='GN'),
            num_convs=4,
            num_fcs=1,
            type='QuasiDenseEmbedHead'),
        roi_extractor=dict(
            featmap_strides=[
                8,
                16,
                32,
            ],
            out_channels=256,
            roi_layer=dict(output_size=7, sampling_ratio=0, type='RoIAlign'),
            type='SingleRoIExtractor'),
        train_cfg=dict(
            assigner=dict(
                ignore_iof_thr=-1,
                match_low_quality=False,
                min_pos_iou=0.5,
                neg_iou_thr=0.3,
                pos_iou_thr=0.7,
                type='MaxIoUAssigner'),
            sampler=dict(
                add_gt_as_proposals=True,
                neg_pos_ub=3,
                neg_sampler=dict(type='RandomSampler'),
                num=512,
                pos_fraction=0.5,
                pos_sampler=dict(type='InstanceBalancedPosSampler'),
                type='CombinedSampler')),
        type='MasaTrackHead'),
    tracker=dict(
        fps=5,
        init_score_thr=0.1,
        match_score_thr=0.5,
        max_distance=100,
        memo_momentum=0.8,
        memo_tracklet_frames=10,
        obj_score_thr=0.01,
        type='MasaTaoTracker',
        with_cats=False),
    train_cfg=dict(
        rcnn=dict(
            assigner=dict(
                ignore_iof_thr=-1,
                match_low_quality=False,
                min_pos_iou=0.5,
                neg_iou_thr=0.5,
                pos_iou_thr=0.5,
                type='MaxIoUAssigner'),
            debug=False,
            pos_weight=-1,
            sampler=dict(
                add_gt_as_proposals=True,
                neg_pos_ub=-1,
                num=512,
                pos_fraction=0.25,
                type='RandomSampler')),
        rpn=dict(
            allowed_border=-1,
            assigner=dict(
                ignore_iof_thr=-1,
                match_low_quality=True,
                min_pos_iou=0.3,
                neg_iou_thr=0.3,
                pos_iou_thr=0.7,
                type='MaxIoUAssigner'),
            debug=False,
            pos_weight=-1,
            sampler=dict(
                add_gt_as_proposals=False,
                neg_pos_ub=-1,
                num=256,
                pos_fraction=0.5,
                type='RandomSampler')),
        rpn_proposal=dict(
            max_per_img=1000,
            min_bbox_size=0,
            nms=dict(iou_threshold=0.7, type='nms'),
            nms_pre=2000)),
    type='MASA',
    unified_backbone=True)
resume = False
test_cfg = dict(type='TestLoop')
train_cfg = None
val_cfg = dict(type='ValLoop')
vis_backends = [
    dict(type='LocalVisBackend'),
]
visualizer = dict(
    name='visualizer',
    type='MasaTrackLocalVisualizer',
    vis_backends=[
        dict(type='LocalVisBackend'),
    ])
